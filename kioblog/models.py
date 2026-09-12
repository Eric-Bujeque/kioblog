import re
from html import unescape

from django.conf import settings
from django.core.cache import cache
from django.db import models, router
from django.db.models.signals import m2m_changed, post_save, pre_delete
from django.utils import timezone
from markdownx.models import MarkdownxField

from kioblog.markdown.render import RenderedContent, render_markdown


class Category(models.Model):
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=200)
    featured = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def post_count(self):
        return self.post_set.filter(draft=False).count()

    class Meta:
        verbose_name_plural = "Categories"


class Tag(models.Model):
    title = models.CharField(max_length=60)
    slug = models.SlugField(max_length=200, unique=True)

    def __str__(self):
        return self.title


class Post(models.Model):
    title = models.CharField(max_length=250)
    content = MarkdownxField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    blocked = models.BooleanField(default=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    created = models.DateField(auto_now_add=True)
    published = models.DateTimeField(default=timezone.now)
    # Distinct from `published`: this tracks edits made after the post went
    # live, so the sitemap's lastmod (see sitemap.py) reflects real changes
    # instead of standing still at the original publish date forever.
    updated = models.DateTimeField(auto_now=True)
    # PostView resolves by slug alone (DetailView.get_object -> .get()), which
    # raises MultipleObjectsReturned - uncaught, a 500 - if two posts share
    # one. See migration 0007 for how this is retrofitted onto existing data.
    slug = models.SlugField(max_length=200, unique=True)
    image = models.FileField(upload_to=settings.UPLOAD_TO, null=True)
    draft = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    excerpt = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    meta_title = models.CharField(null=True, blank=True, max_length=250)
    meta_description = models.CharField(null=True, blank=True, max_length=250)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-published", "-id"]

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        # save(update_fields=[...]) that omits "updated" would otherwise skip
        # auto_now entirely - Django's _save_table only calls pre_save() (what
        # auto_now relies on) for fields actually listed in update_fields.
        # Confirmed against Django's own source and a standalone repro:
        # post.save(update_fields=["content"]) left `updated` untouched, which
        # would make the sitemap's lastmod (see sitemap.py) silently stop
        # reflecting edits made through any partial save.
        #
        # An explicit Django-matching signature, not (self, *args, **kwargs):
        # Model.save()'s real signature takes update_fields positionally too
        # (save(force_insert, force_update, using, update_fields)) - reading
        # it only from kwargs let a positional call
        # (post.save(False, False, None, ["content"])) skip this override,
        # and the partial save it requested, entirely. Copilot finding, real
        # - naming every parameter the same way Django does makes Python's
        # own argument binding handle both call styles identically.
        #
        # Checked on a *truthy* update_fields, not just "is not None": Django
        # treats an explicitly empty update_fields ([] or set()) as "skip the
        # save entirely" - confirmed in Model.save()'s own source, `if not
        # update_fields: return`, before touching the database at all. Firing
        # on `is not None` would have turned that intentional no-op into a
        # real write of just {"updated"}.
        #
        # Materialized into a set before that truthiness check, not checked
        # on the raw argument: update_fields is documented as any iterable,
        # and a generator is a truthy *object* even when it would yield
        # nothing once consumed - `if update_fields:` on the raw value can't
        # tell "empty" from "has items" without consuming it first, so an
        # explicitly empty generator would still reach the branch below and
        # turn Django's own empty-iterable no-op into a real write of just
        # {"updated"}, exactly the bug the truthy check above exists to
        # avoid for a plain empty list. Reassigned unconditionally, not just
        # inside the truthy branch: passing the exhausted-if-empty generator
        # through unchanged would hand Django's own save() a still-truthy
        # object whose own `if not update_fields: return` no-op wouldn't
        # catch it either, and it would go on to re-consume the same
        # exhausted generator itself, hitting its own internal assertion
        # instead of cleanly no-op'ing (confirmed this exact ordering raised
        # AssertionError in Model.save_base() before fixing it this way).
        #
        # `using` resolved through the router exactly once, here, and reused
        # for both the deferred-field decision below and the super().save()
        # call at the end - not left as None for Django to resolve a second
        # time on its own, which could hand back a different alias for a
        # router whose answer isn't stable across calls.
        using = using or router.db_for_write(self.__class__, instance=self)
        if update_fields is not None:
            update_fields = set(update_fields)
            if update_fields:
                update_fields.add("updated")
        elif self.pk is not None and not force_insert:
            # Copilot finding, real: a bare save() with no explicit
            # update_fields is usually a full save - every field (including
            # "updated") gets pre_save() called normally. Except for a
            # *deferred* instance (Post.objects.only("content").get(...)):
            # Django's own save() then auto-restricts the write to whichever
            # fields were actually loaded - "updated" was never one of them,
            # so it was silently excluded, leaving lastmod stale for exactly
            # this kind of implicit partial save. Mirrors Model.save()'s own
            # deferred-field detection (confirmed against Django 3.2's
            # source, including its `using == self._state.db` guard - this
            # shortcut is only valid when saving to the same alias the
            # instance was loaded from) to pre-empt it with the same
            # update_fields Django would have computed anyway, plus
            # "updated". Already fixed this exact way on PR #15's own
            # save() override; applied the same fix here.
            deferred = self.get_deferred_fields()
            if deferred and using == self._state.db:
                field_names = {
                    f.attname for f in self._meta.concrete_fields if not f.primary_key and not hasattr(f, "through")
                }
                loaded = field_names - deferred
                if loaded:
                    update_fields = {*loaded, "updated"}
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)

    def _render_cache_key(self):
        # None for an unsaved instance: there's no pk yet, and `updated` isn't
        # set until the first save() (auto_now). _render() below falls back
        # to the existing per-instance-only caching for that case, which
        # already handles it correctly - it never touches the DB or cache.
        if self.pk is None:
            return None
        return f"kioblog:post:{self.pk}:render:{self.updated.isoformat()}"

    def _render(self):
        if not hasattr(self, "_rendered"):
            cache_key = self._render_cache_key()
            cached = cache.get(cache_key) if cache_key else None
            if cached is not None:
                # RenderedContent (a str subclass carrying .html/.toc as
                # extra attributes) isn't picklable as-is - its __new__
                # requires `toc`, which pickle's default str-subclass
                # reconstruction doesn't know to supply. Verified this
                # empirically (pickle.loads raised TypeError) before caching
                # the plain (html, toc) tuple instead of the object itself.
                html, toc = cached
                self._rendered = RenderedContent(html, toc)
            else:
                self._rendered = render_markdown(self.content)
                if cache_key:
                    # No timeout: invalidation is the cache key changing
                    # (bumped by `updated` on every save), not an expiry -
                    # the old key just becomes unreferenced dead weight for
                    # the cache backend's own eviction policy to reclaim.
                    cache.set(cache_key, (self._rendered.html, self._rendered.toc), timeout=None)
        return self._rendered

    @property
    def content_html(self):
        return self._render().html

    @property
    def toc(self):
        return self._render().toc

    @property
    def reading_time(self):
        words = len(re.sub(r"<[^>]+>", "", self.content_html).split())
        return max(1, round(words / 200))

    def first_paragraph(self):
        re_pattern = re.compile(r"(<p.*?</p>)")
        paragraphs = re_pattern.search(self.content)
        if not paragraphs:
            return ""
        return paragraphs.groups()[0]

    @property
    def display_excerpt(self):
        if self.excerpt:
            return self.excerpt
        match = re.search(r"<p[^>]*>(.*?)</p>", self.content_html, re.DOTALL)
        if not match:
            return ""
        text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return unescape(text)

    def get_previous(self):
        tie_break = models.Q(published__lt=self.published) | models.Q(published=self.published, id__lt=self.id)
        return Post.objects.filter(draft=False).filter(tie_break).order_by("-published", "-id").first()

    def get_next(self):
        tie_break = models.Q(published__gt=self.published) | models.Q(published=self.published, id__gt=self.id)
        return Post.objects.filter(draft=False).filter(tie_break).order_by("published", "id").first()

    def related_posts(self, limit=4):
        qs = (
            Post.objects.filter(draft=False)
            .exclude(pk=self.pk)
            .filter(models.Q(category=self.category) | models.Q(tags__in=self.tags.all()))
            .distinct()
        )
        return qs[:limit]

    @staticmethod
    def get_recent_posts(current_slug=None):
        recent_posts = Post.objects.filter(draft=False)
        if current_slug is not None:
            recent_posts = recent_posts.exclude(slug=current_slug)
        return recent_posts[:5]


def _bump_updated_on_tag_change(sender, instance, action, reverse, using, pk_set, **kwargs):
    # Copilot finding, real: auto_now only runs when Post.save() actually
    # executes, but ManyToManyField.add()/remove()/clear() write straight to
    # the through table and never call save() at all - a post's tags are
    # part of what post.html renders, so changing only the tags (through the
    # admin's own tags widget, e.g.) left `updated`, and so the sitemap's
    # lastmod, standing still even though the page's content changed.
    #
    # post_add/post_remove/post_clear, not the pre_* variants (except
    # pre_clear below, for a narrower reason): those fire after the
    # through-table write has actually happened, matching when save()'s own
    # post_save would normally fire for a content edit - bumping updated on
    # the pre_* signals would move it even if the underlying
    # add()/remove()/clear() call went on to fail.
    if not reverse:
        # Forward direction (post.tags.add/remove/clear(...)): `instance` is
        # the Post itself. save(update_fields=["updated"]) rather than a
        # bare save() - a bare save() would re-run pre_save on every field
        # via a full UPDATE for no reason, only `updated` itself actually
        # needs touching here. Passing it through this override (not
        # .update()) so auto_now still does the actual timestamping, the
        # same single source of truth every other partial save in this file
        # already goes through.
        #
        # `using=using`, not left for Post.save()'s own router resolution to
        # pick: m2m_changed's `using` names the alias the through-row change
        # actually ran against, matching the reverse branches below - Copilot
        # finding, real, for a router that could route the through table
        # differently than a bare Post instance.
        if action == "pre_clear":
            # Copilot finding, real: post.tags.clear() on a post with no
            # tags is a genuine no-op, but bumping unconditionally on
            # post_clear (as this used to) moved `updated` - and so the
            # sitemap's lastmod - for a page that didn't actually change.
            # Checked here, before the through rows are gone, the same
            # single-query approach as the reverse direction's own
            # pre_clear handling below: a no-op (0 rows matched) when there
            # was nothing to clear.
            Post.objects.using(using).filter(pk=instance.pk, tags__isnull=False).update(updated=timezone.now())
        elif action == "post_add":
            # Guarded on pk_set, unlike post_remove below: Django's own
            # _add_items sends pk_set as the target ids that were actually
            # *missing* before this call (confirmed against Django's
            # source) - re-adding an already-present tag fires post_add
            # with an empty pk_set, a genuine no-op this skips bumping for.
            if pk_set:
                instance.save(using=using, update_fields=["updated"])
        elif action == "post_remove":
            # NOT guarded on pk_set the way post_add is above: Django's own
            # _remove_items sends pk_set as the *requested* ids to remove,
            # not the ones actually found and deleted (confirmed against
            # Django's source) - it stays non-empty even for a genuine
            # no-op remove (a tag that was never attached to begin with).
            # Left unguarded rather than chasing that precisely, which
            # would need the same pre_remove-capture-and-diff complexity as
            # pre_clear above, for a rare, low-consequence edge case: an
            # extra lastmod bump for a removal that changed nothing, not a
            # correctness bug the way a *missed* edit would be.
            instance.save(using=using, update_fields=["updated"])
        return

    # Reverse direction (some_tag.posts.add/remove/clear(post, ...), via
    # this field's related_name="posts"): `instance` is the Tag, not a
    # Post, and Tag has no `updated` field at all - naively reusing the
    # forward branch's instance.save() would raise. Copilot finding, real:
    # the affected Posts (named by pk_set for add/remove) still need their
    # `updated` bumped, the same as the forward direction - a post's
    # rendered tags changed here too, just reached from the Tag side.
    #
    # `using`, not the default manager, for every query below: m2m_changed
    # supplies the alias the relation change is actually running against
    # (tag.posts.using("replica").add(...)) - Copilot finding, real; using
    # the default manager instead could bump `updated` on the wrong
    # database, or not at all, for a non-default alias.
    if action == "pre_clear":
        # A single UPDATE ... WHERE tags = instance, not a Python-side pk
        # set captured here and bulk-updated at post_clear: pk_set is
        # documented as None for post_clear specifically (the through rows
        # are already gone by then), and materializing every affected pk
        # into memory first doesn't scale to a tag used by many posts -
        # Copilot finding, real. Run while the through rows this filters on
        # still exist (pre_clear, before the delete), and safe to run here
        # rather than at post_clear: Django's own ManyRelatedManager.clear()
        # wraps pre_clear, the through-row delete, and post_clear in one
        # transaction.atomic(using=db) - if clear() goes on to fail, this
        # update rolls back with it, the same as the forward direction's
        # "only bump on the post_* signals" reasoning above achieves by
        # ordering instead.
        Post.objects.using(using).filter(tags=instance).update(updated=timezone.now())
    elif action == "post_add":
        # Guarded on pk_set, same reasoning and same Django source as the
        # forward direction's post_add above (this is the same
        # ManyRelatedManager._add_items() either way, just with `reverse`
        # toggling what `instance` means) - pk_set is empty for a genuine
        # no-op re-add.
        if pk_set:
            Post.objects.using(using).filter(pk__in=pk_set).update(updated=timezone.now())
    elif action == "post_remove":
        # NOT guarded on pk_set, same reasoning as the forward direction's
        # post_remove above: pk_set here is the *requested* ids (old_ids in
        # Django's _remove_items), not the ones actually found and deleted,
        # so it's always truthy whenever this signal fires at all - a
        # no-op guard here wouldn't catch some_tag.posts.remove(post) for a
        # post that was never attached. Same accepted, documented
        # imprecision as the forward direction, not fixed here for the
        # same reason: a real fix needs the same pre_remove-capture-and-
        # diff complexity as pre_clear above, for a rare, low-consequence
        # edge case.
        if pk_set:
            Post.objects.using(using).filter(pk__in=pk_set).update(updated=timezone.now())


def _bump_updated_on_tag_edit(sender, instance, created, using, update_fields, **kwargs):
    # A Tag's title/slug is rendered on every post that has it (the tag
    # links in post.html: `<a href="{% url 'kioblog-tag' tag.slug %}">#{{
    # tag.title }}</a>`) - editing either changes those posts' public pages
    # without ever touching Post itself, the same kind of gap m2m_changed
    # exists to close for adding/removing a tag from a post. Copilot
    # finding, real.
    #
    # `not created`: a brand-new tag can't be attached to any post yet at
    # the moment this fires - nothing could reference it before it existed
    # - so there's nothing to bump; skip the query entirely rather than
    # running a no-op UPDATE on every tag creation.
    #
    # Also guarded on which fields actually changed, not just "was this a
    # real edit": Tag has no fields today besides title/slug, but
    # post_save's own update_fields (None for a full save, the field names
    # for a partial one) is checked anyway, on the same reasoning as the
    # Category receiver below - Copilot finding there, applying the same
    # fix here for consistency and against a future field this wouldn't
    # otherwise guard.
    if not created and (update_fields is None or update_fields & {"title", "slug"}):
        Post.objects.using(using).filter(tags=instance).update(updated=timezone.now())


def _bump_updated_on_tag_delete(sender, instance, using, **kwargs):
    # Deleting a Tag removes it from every post's rendered tag list too,
    # but that happens via Django's own cascade-delete of the through rows,
    # not through m2m_changed - that signal only fires for add()/remove()/
    # clear()/set() calls on a live manager, never for a model deletion
    # cascading into the through table. Copilot finding, real.
    #
    # pre_delete, not post_delete: by post_delete the through rows (and so
    # this filter) are already gone. Model.delete() wraps pre_delete, the
    # cascade, and post_delete in one transaction, same reasoning as
    # pre_clear above for why running the update here is still safe if the
    # delete itself goes on to fail.
    Post.objects.using(using).filter(tags=instance).update(updated=timezone.now())


def _bump_updated_on_category_edit(sender, instance, created, using, update_fields, **kwargs):
    # Copilot finding, real: post.html renders post.category.title directly
    # - editing it changes every one of that category's posts' public pages
    # without ever touching Post itself, the same gap the Tag receivers
    # above close for tags. No matching delete receiver needed: Post.category
    # is on_delete=CASCADE, so deleting a Category deletes its posts along
    # with it - there's no post left with a stale lastmod to bump.
    #
    # `not created`: a brand-new category can't be attached to any post yet
    # at the moment this fires, so there's nothing to bump.
    #
    # Guarded on update_fields too, not just "was this a save at all":
    # Category also has `featured` and `slug`, neither of which post.html
    # renders (only category.title is) - category.save(update_fields=
    # ["featured"]) used to bump every one of that category's posts'
    # lastmod anyway, wrongly signalling a page change (and a possible
    # recrawl) for a field the public post page doesn't show. update_fields
    # is None for a bare save() (bump - can't tell what changed, so assume
    # everything did, the same conservative default every other receiver
    # here uses) or the actual field names for a partial one.
    if not created and (update_fields is None or "title" in update_fields):
        Post.objects.using(using).filter(category=instance).update(updated=timezone.now())


m2m_changed.connect(_bump_updated_on_tag_change, sender=Post.tags.through)
post_save.connect(_bump_updated_on_tag_edit, sender=Tag)
pre_delete.connect(_bump_updated_on_tag_delete, sender=Tag)
post_save.connect(_bump_updated_on_category_edit, sender=Category)


class Comment(models.Model):
    username = models.CharField(max_length=100)
    content = models.TextField()
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True)
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)
    created = models.DateField(auto_now_add=True)
    email = models.EmailField()
    api = models.CharField(null=True, blank=True, max_length=50)

    def __str__(self):
        return f"{self.username} - {self.post}"


class Meta(models.Model):
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=250, null=True)

    def __str__(self):
        return self.key
