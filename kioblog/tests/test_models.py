from django.db import IntegrityError, transaction
from django.utils import timezone

from kioblog import models
from kioblog.tests import base


class KioblogModels(base.BaseTestCase):
    def test_post_first_paragraph(self) -> None:
        first_paragraph = "<p>first paragraph</p>"
        self.post.content = f"{first_paragraph}<p>Second</p>"
        self.assertEqual(self.post.first_paragraph(), first_paragraph)

    def test_post_get_recent_posts_no_current(self) -> None:
        self.assertIn(self.post, models.Post.get_recent_posts())

    def test_post_get_recent_posts_current(self) -> None:
        self.assertNotIn(self.post, models.Post.get_recent_posts(self.post.slug))

    def test_content_html_renders_markdown(self) -> None:
        self.post.content = "# Heading\n\nBody text."
        self.assertIn('<h2 id="heading">Heading</h2>', self.post.content_html)
        self.assertIn("<p>Body text.</p>", self.post.content_html)

    def test_reading_time_at_least_one_minute(self) -> None:
        self.assertGreaterEqual(self.post.reading_time, 1)

    def test_get_previous_and_next_are_nearest_neighbours(self) -> None:
        now = timezone.now()
        older = models.Post.objects.create(
            title="older",
            content="x",
            user=self.user,
            category=self.category,
            slug="older",
            published=now - timezone.timedelta(days=2),
        )
        newer = models.Post.objects.create(
            title="newer",
            content="x",
            user=self.user,
            category=self.category,
            slug="newer",
            published=now + timezone.timedelta(days=2),
        )
        self.assertEqual(self.post.get_previous(), older)
        self.assertEqual(self.post.get_next(), newer)

    def test_display_excerpt_prefers_explicit_excerpt(self) -> None:
        self.post.excerpt = "A hand-written summary."
        self.post.content = "# Heading\n\nRendered paragraph text."
        self.assertEqual(self.post.display_excerpt, "A hand-written summary.")

    def test_display_excerpt_falls_back_to_rendered_content(self) -> None:
        self.post.excerpt = ""
        self.post.content = "# Heading\n\nRendered paragraph text."
        self.assertEqual(self.post.display_excerpt, "Rendered paragraph text.")

    def test_display_excerpt_unescapes_html_entities(self) -> None:
        self.post.excerpt = ""
        self.post.content = "AT&T sells `<x>` gadgets."
        self.assertEqual(self.post.display_excerpt, "AT&T sells <x> gadgets.")

    def test_get_previous_and_next_break_ties_on_same_published(self) -> None:
        same_time = timezone.now()
        p1 = models.Post.objects.create(
            title="tie-1", content="x", user=self.user, category=self.category, slug="tie-1", published=same_time
        )
        p2 = models.Post.objects.create(
            title="tie-2", content="x", user=self.user, category=self.category, slug="tie-2", published=same_time
        )
        p3 = models.Post.objects.create(
            title="tie-3", content="x", user=self.user, category=self.category, slug="tie-3", published=same_time
        )
        # Same published (e.g. midnight-backfilled posts); ordering falls back to id.
        self.assertEqual(p2.get_previous(), p1)
        self.assertEqual(p2.get_next(), p3)

    def test_related_posts_share_category_and_exclude_self(self) -> None:
        sibling = models.Post.objects.create(
            title="sibling", content="x", user=self.user, category=self.category, slug="sibling"
        )
        related = self.post.related_posts()
        self.assertIn(sibling, related)
        self.assertNotIn(self.post, related)

    def test_post_slug_must_be_unique(self) -> None:
        # Without this, two posts sharing a slug make PostView 500 instead of
        # serving either one - see migration 0007 for the full mechanism.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                models.Post.objects.create(
                    title="duplicate", content="x", user=self.user, category=self.category, slug=self.post.slug
                )

    def test_category_post_count_ignores_drafts(self) -> None:
        models.Post.objects.create(
            title="draft", content="x", user=self.user, category=self.category, slug="draft", draft=True
        )
        # self.post (non-draft) counts, the draft does not.
        self.assertEqual(self.category.post_count(), 1)

    def test_an_empty_update_fields_generator_stays_a_no_op(self) -> None:
        # Copilot finding, real: update_fields is documented as any iterable,
        # and a generator is a truthy *object* even when it would yield
        # nothing once consumed - `if update_fields:` on the raw generator
        # can't tell "empty" from "has items" without consuming it first.
        # Unlike an empty list/set (already handled), an unconsumed empty
        # generator used to pass that truthy check, adding "updated" and
        # turning Django's own empty-iterable no-op (`if not update_fields:
        # return`, in Model.save() itself) into a real write of just
        # {"updated"}.
        before = self.post.updated
        self.post.title = "should not be saved"
        self.post.save(update_fields=(name for name in ()))

        self.post.refresh_from_db()
        self.assertEqual(self.post.updated, before)
        self.assertNotEqual(self.post.title, "should not be saved")

    def test_update_fields_passed_positionally_still_bumps_updated(self) -> None:
        # Copilot finding, real: Model.save()'s actual signature is
        # save(force_insert, force_update, using, update_fields) -
        # update_fields can be passed positionally, not only as a keyword.
        # Reading it exclusively from kwargs (the old *args, **kwargs
        # signature) let a positional call like this one skip this override,
        # and the partial save it requested, entirely - auto_now would then
        # never run, leaving `updated` (and so the sitemap's lastmod) stale.
        backdated = timezone.now() - timezone.timedelta(days=1)
        models.Post.objects.filter(pk=self.post.pk).update(updated=backdated)

        stale = models.Post.objects.get(pk=self.post.pk)
        stale.content = "# Positional save"
        stale.save(False, False, None, ["content"])

        fresh = models.Post.objects.get(pk=self.post.pk)
        self.assertGreater(fresh.updated, backdated)
        self.assertEqual(fresh.content, "# Positional save")

    def test_a_deferred_instances_implicit_save_still_bumps_updated(self) -> None:
        # Copilot finding, real: Post.objects.only("content").get(...);
        # post.content = ...; post.save() - no explicit update_fields at
        # all. Django's own save() then auto-restricts the write to the
        # fields that were actually *loaded* (a deferred-instance
        # optimization, confirmed against Django 3.2's own source) -
        # "updated" was never among them, so without handling this case
        # specifically it's silently excluded, leaving lastmod stale for
        # exactly this kind of implicit partial save.
        backdated = timezone.now() - timezone.timedelta(days=1)
        models.Post.objects.filter(pk=self.post.pk).update(updated=backdated)

        deferred = models.Post.objects.only("content").get(pk=self.post.pk)
        deferred.content = "# Deferred instance save"
        deferred.save()

        fresh = models.Post.objects.get(pk=self.post.pk)
        self.assertGreater(fresh.updated, backdated)

    def _backdate_post(self):
        backdated = timezone.now() - timezone.timedelta(days=1)
        models.Post.objects.filter(pk=self.post.pk).update(updated=backdated)
        return backdated

    def test_adding_a_tag_bumps_updated(self) -> None:
        # Copilot finding, real: ManyToManyField.add()/remove()/clear() write
        # straight to the through table and never call Post.save() at all,
        # so auto_now never ran for a tags-only change - even though a
        # post's tags are part of what post.html renders, leaving the
        # sitemap's lastmod standing still for an edit that changed the
        # public page.
        backdated = self._backdate_post()
        tag = models.Tag.objects.create(title="new tag", slug="new-tag")

        self.post.tags.add(tag)

        self.post.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)

    def test_removing_a_tag_bumps_updated(self) -> None:
        tag = models.Tag.objects.create(title="removable", slug="removable")
        self.post.tags.add(tag)
        backdated = self._backdate_post()

        self.post.tags.remove(tag)

        self.post.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)

    def test_clearing_tags_bumps_updated(self) -> None:
        tag = models.Tag.objects.create(title="clearable", slug="clearable")
        self.post.tags.add(tag)
        backdated = self._backdate_post()

        self.post.tags.clear()

        self.post.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)

    def test_readding_an_already_present_tag_does_not_bump_updated(self) -> None:
        # Copilot finding, real: Django still fires post_add for a re-add
        # that changed nothing - confirmed against its own _add_items
        # source, which sends pk_set as only the ids that were actually
        # *missing* beforehand, empty for this case. Bumping unconditionally
        # would move the sitemap's lastmod for a page that didn't change.
        tag = models.Tag.objects.create(title="already there", slug="already-there")
        self.post.tags.add(tag)
        backdated = self._backdate_post()

        self.post.tags.add(tag)

        self.post.refresh_from_db()
        self.assertEqual(self.post.updated, backdated)

    def test_clearing_an_already_tagless_post_does_not_bump_updated(self) -> None:
        # Copilot finding, real: post.tags.clear() on a post with no tags
        # is a genuine no-op - confirmed nothing was tagged, so nothing
        # should move.
        backdated = self._backdate_post()
        self.assertFalse(self.post.tags.exists())

        self.post.tags.clear()

        self.post.refresh_from_db()
        self.assertEqual(self.post.updated, backdated)

    def test_adding_a_post_from_the_reverse_tag_manager_bumps_updated(self) -> None:
        # The same m2m_changed signal also fires for the reverse direction
        # (some_tag.posts.add(post), via the M2M's related_name="posts") -
        # there, `instance` is the Tag, not a Post, and Tag has no `updated`
        # field at all, so naively reusing the forward branch would raise
        # FieldError. Copilot finding, real: the affected Post's tags
        # changed here too, just reached from the Tag side - it still needs
        # `updated` bumped, not just avoid crashing.
        backdated = self._backdate_post()
        tag = models.Tag.objects.create(title="reverse add", slug="reverse-add")

        tag.posts.add(self.post)

        self.post.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)

    def test_removing_a_post_from_the_reverse_tag_manager_bumps_updated(self) -> None:
        tag = models.Tag.objects.create(title="reverse remove", slug="reverse-remove")
        tag.posts.add(self.post)
        backdated = self._backdate_post()

        tag.posts.remove(self.post)

        self.post.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)

    def test_clearing_a_tags_posts_bumps_updated_on_all_of_them(self) -> None:
        # post_clear's pk_set is None (Django's own m2m_changed contract) -
        # the affected posts are bumped at pre_clear instead, while the
        # through rows they're matched through still exist.
        tag = models.Tag.objects.create(title="reverse clear", slug="reverse-clear")
        other = models.Post.objects.create(
            title="other", content="x", user=self.user, category=self.category, slug="other-tagged"
        )
        tag.posts.add(self.post, other)
        backdated = self._backdate_post()
        models.Post.objects.filter(pk=other.pk).update(updated=backdated)

        tag.posts.clear()

        self.post.refresh_from_db()
        other.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)
        self.assertGreater(other.updated, backdated)

    def test_editing_a_tags_title_bumps_updated_on_its_posts(self) -> None:
        # Copilot finding, real: a Tag's title/slug is rendered on every
        # post that has it (the tag links in post.html) - editing either
        # changes those posts' public pages without Post.save() ever
        # running, the same kind of gap m2m_changed closes for adding or
        # removing a tag from a post.
        tag = models.Tag.objects.create(title="editable", slug="editable")
        tag.posts.add(self.post)
        backdated = self._backdate_post()

        tag.title = "edited title"
        tag.save()

        self.post.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)

    def test_creating_a_tag_does_not_touch_any_post(self) -> None:
        # A brand-new tag can't be attached to any post yet at the moment
        # its own post_save fires - nothing could reference it before it
        # existed - so creating one must not bump anything.
        backdated = self._backdate_post()

        models.Tag.objects.create(title="brand new", slug="brand-new")

        self.post.refresh_from_db()
        self.assertEqual(self.post.updated, backdated)

    def test_deleting_a_tag_bumps_updated_on_its_posts(self) -> None:
        # Copilot finding, real: deleting a Tag removes it from every
        # post's rendered tag list too, via Django's own cascade-delete of
        # the through rows - but that never fires m2m_changed (that signal
        # only fires for add()/remove()/clear()/set() calls on a live
        # manager, not a model deletion cascading into the through table),
        # so without its own receiver this left `updated` stale.
        tag = models.Tag.objects.create(title="deletable", slug="deletable")
        tag.posts.add(self.post)
        backdated = self._backdate_post()

        tag.delete()

        self.post.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)

    def test_editing_a_categorys_title_bumps_updated_on_its_posts(self) -> None:
        # Copilot finding, real: post.html renders post.category.title
        # directly - editing it changes every one of that category's posts'
        # public pages without Post.save() ever running, mirroring the Tag
        # edit receiver above.
        backdated = self._backdate_post()

        self.category.title = "renamed category"
        self.category.save()

        self.post.refresh_from_db()
        self.assertGreater(self.post.updated, backdated)

    def test_creating_a_category_does_not_touch_any_post(self) -> None:
        # A brand-new category can't be attached to any post yet at the
        # moment its own post_save fires, so creating one must not bump
        # anything - mirrors test_creating_a_tag_does_not_touch_any_post.
        backdated = self._backdate_post()

        models.Category.objects.create(title="brand new category", slug="brand-new-category")

        self.post.refresh_from_db()
        self.assertEqual(self.post.updated, backdated)
