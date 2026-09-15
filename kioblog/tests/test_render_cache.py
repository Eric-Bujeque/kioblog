"""Post._render() caches Markdown+Pygments rendering across requests (via
django.core.cache), not just within one Python instance's lifetime the way it
always has. Each test re-fetches the post as a fresh instance to simulate
what actually happens across two HTTP requests - Post._rendered (the
per-instance cache) never survives that, only the cross-request one could.
"""

from unittest.mock import ANY, MagicMock, patch

from django.core.cache import cache
from django.utils import timezone

from kioblog import models
from kioblog.markdown.render import render_markdown
from kioblog.tests import base


class RenderCacheTests(base.BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        # django.core.cache.cache is a process-global LocMemCache that
        # Django's test runner does NOT reset between tests the way it does
        # the database (each test only rolls back its own transaction).
        # Content-hashed keys make that collide across tests for real: every
        # test's SQLite autoincrement restarts at the same pk after rollback
        # (confirmed - self.post.pk is 1 in every test), and BaseTestCase
        # always gives self.post the same content ("Foo Bar"), so a prior
        # test's cache entry for pk=1 + that content stays valid and hides a
        # cache miss this test meant to exercise. Caught exactly this way:
        # test_second_request_hits_the_cache_instead_of_re_rendering saw 0
        # render_markdown calls instead of 1, because an earlier test in the
        # same run had already warmed that same key.
        cache.clear()

    def test_second_request_hits_the_cache_instead_of_re_rendering(self) -> None:
        with patch("kioblog.models.render_markdown", MagicMock(side_effect=render_markdown)) as mocked:
            _ = models.Post.objects.get(pk=self.post.pk).content_html
            _ = models.Post.objects.get(pk=self.post.pk).content_html
            self.assertEqual(mocked.call_count, 1)

    def test_cached_html_and_toc_match_a_fresh_render(self) -> None:
        # Exercises the real cache round-trip (LocMemCache genuinely pickles,
        # confirmed separately) rather than only the freshly-rendered path -
        # this is what would have caught RenderedContent not being picklable
        # as-is (its __new__ requires `toc`; pickle's default reconstruction
        # for a str subclass doesn't know to supply it).
        first = models.Post.objects.get(pk=self.post.pk)
        expected_html, expected_toc = first.content_html, first.toc

        second = models.Post.objects.get(pk=self.post.pk)
        self.assertEqual(second.content_html, expected_html)
        self.assertEqual(second.toc, expected_toc)

    def test_editing_the_post_invalidates_the_cached_render(self) -> None:
        _ = models.Post.objects.get(pk=self.post.pk).content_html  # populate the cache

        stale = models.Post.objects.get(pk=self.post.pk)
        stale.content = "# A brand new heading"
        stale.save()  # the cache key is a hash of content, so this alone busts it

        fresh = models.Post.objects.get(pk=self.post.pk)
        self.assertIn("A brand new heading", fresh.content_html)
        self.assertNotIn(self.post.content, fresh.content_html)

    def test_unsaved_in_memory_edit_is_not_served_stale(self) -> None:
        # The cache key is a hash of self.content specifically so this works:
        # render_markdown is a pure function of content alone, so an in-memory
        # change - never saved - already makes the hash (and so the cache
        # lookup) reflect it. A pk+`updated`-based key could not: `updated`
        # only moves on save(), so it would still point at the old render.
        _ = models.Post.objects.get(pk=self.post.pk).content_html  # populate the cache

        dirty = models.Post.objects.get(pk=self.post.pk)
        dirty.content = "# Never saved"
        self.assertIn("Never saved", dirty.content_html)

    def test_manually_assigned_pk_on_an_unsaved_post_does_not_crash(self) -> None:
        # An unsaved instance can still have a pk if one was assigned by hand
        # (self.pk is None is false here) - `updated` would still be None in
        # that case (auto_now only sets it on save()), so a key built from it
        # would raise. The content-hash key never touches `updated`.
        unsaved = models.Post(pk=999999, title="draft", content="# Manual pk", user=self.user, category=self.category)
        self.assertIsNotNone(unsaved.pk)
        self.assertIsNone(unsaved.updated)
        self.assertIn("Manual pk", unsaved.content_html)

    def test_partial_save_still_invalidates_the_cache(self) -> None:
        # save(update_fields=[...]) that omits "updated" would otherwise skip
        # auto_now entirely (confirmed against Django's own _save_table:
        # pre_save() only runs for fields actually listed in update_fields),
        # leaving the cache key unchanged and serving stale HTML for new
        # content. Backdates `updated` via .update() (bypasses save()/auto_now
        # entirely) rather than a real time delay, so this can't flake on a
        # fast test run producing two identical microsecond timestamps.
        _ = models.Post.objects.get(pk=self.post.pk).content_html  # populate the cache
        backdated = timezone.now() - timezone.timedelta(days=1)
        models.Post.objects.filter(pk=self.post.pk).update(updated=backdated)

        stale = models.Post.objects.get(pk=self.post.pk)
        stale.content = "# Partial save heading"
        stale.save(update_fields=["content"])

        fresh = models.Post.objects.get(pk=self.post.pk)
        self.assertGreater(fresh.updated, backdated)
        self.assertIn("Partial save heading", fresh.content_html)

    def test_explicitly_empty_update_fields_stays_a_no_op(self) -> None:
        # Django treats update_fields=[] as "skip the save entirely" (Model.
        # save()'s own source: `if not update_fields: return`, before the
        # database is touched at all) - forcing "updated" into it on an
        # `is not None` check rather than a truthy one would turn that
        # intentional no-op into a real write of just {"updated"}.
        before = models.Post.objects.get(pk=self.post.pk).updated
        self.post.title = "should not be saved"
        self.post.save(update_fields=[])

        after = models.Post.objects.get(pk=self.post.pk)
        self.assertEqual(after.updated, before)
        self.assertNotEqual(after.title, "should not be saved")

    def test_an_empty_generator_also_stays_a_no_op(self) -> None:
        # A generator is a truthy *object* even when it would yield nothing
        # once consumed - unlike a list or set, checking `if update_fields:`
        # on the raw generator can't tell "empty" from "has items" without
        # materializing it first. Same contract as the list case above, a
        # different way to reach it.
        before = models.Post.objects.get(pk=self.post.pk).updated
        self.post.title = "should not be saved"
        self.post.save(update_fields=(name for name in ()))

        after = models.Post.objects.get(pk=self.post.pk)
        self.assertEqual(after.updated, before)
        self.assertNotEqual(after.title, "should not be saved")

    def test_update_fields_passed_positionally_still_bumps_updated(self) -> None:
        # Model.save()'s real signature is save(force_insert, force_update,
        # using, update_fields) - update_fields can be passed positionally,
        # not only as a keyword. Reading it exclusively from kwargs would let
        # a positional call skip this override, and the partial save it
        # requested, entirely.
        backdated = timezone.now() - timezone.timedelta(days=1)
        models.Post.objects.filter(pk=self.post.pk).update(updated=backdated)

        stale = models.Post.objects.get(pk=self.post.pk)
        stale.content = "# Positional update_fields"
        stale.save(False, False, None, ["content"])

        fresh = models.Post.objects.get(pk=self.post.pk)
        self.assertGreater(fresh.updated, backdated)

    def test_a_deferred_instances_implicit_save_still_bumps_updated(self) -> None:
        # Post.objects.only("content").get(...); post.content = ...;
        # post.save() - no explicit update_fields at all. Django's own
        # save() then auto-restricts the write to the fields that were
        # actually *loaded* (a deferred-instance optimization, confirmed
        # against Django 3.2's own source) - "updated" was never among them,
        # so without handling this case specifically it's silently excluded,
        # the same staleness as an explicit partial save reaches without the
        # caller ever naming update_fields themselves.
        backdated = timezone.now() - timezone.timedelta(days=1)
        models.Post.objects.filter(pk=self.post.pk).update(updated=backdated)

        deferred = models.Post.objects.only("content").get(pk=self.post.pk)
        deferred.content = "# Deferred instance save"
        deferred.save()

        fresh = models.Post.objects.get(pk=self.post.pk)
        self.assertGreater(fresh.updated, backdated)

    def test_a_deferred_instance_saved_to_a_different_alias_is_not_field_restricted(self) -> None:
        # save(using="other") on a deferred instance must NOT take the
        # "restrict to loaded fields" shortcut above - Django's own
        # condition for it (base.py) is `using == self._state.db`, not just
        # "deferred fields exist". Skipping that check would silently write
        # only the loaded fields (plus "updated") to the target alias,
        # leaving every field the instance never loaded (title, slug, ...)
        # untouched there instead of a full row - exactly the kind of
        # cross-database copy Django's own guard exists to protect against.
        #
        # Patches django.db.models.Model.save (what super().save() resolves
        # to) rather than exercising a real second alias - this repo's dev
        # settings only configure "default", and the point here is proving
        # what update_fields Post.save() computes and hands upward, not
        # exercising a real multi-database write.
        deferred = models.Post.objects.only("content").get(pk=self.post.pk)
        deferred.content = "# Cross-database save"

        with patch("django.db.models.Model.save") as mocked_save:
            deferred.save(using="other")

        mocked_save.assert_called_once_with(force_insert=False, force_update=False, using="other", update_fields=None)

    def test_using_is_resolved_through_the_router_only_once(self) -> None:
        # Copilot finding, real: `using` used to be resolved through the
        # router only for the deferred-field comparison above, then handed
        # to super().save() unresolved (using=None if the caller never
        # passed one) - which resolves it itself, a second time, internally.
        # A router whose db_for_write() isn't stable across calls (a
        # round-robin router over read replicas, for instance) could then
        # decide the shortcut against one alias while the actual write goes
        # to a different one it returned on the second call.
        #
        # Proven by call count, not a second real database (this repo's dev
        # settings only configure "default"): resolving `using` once, up
        # front, and passing that same value through to super().save()
        # means Django's own internal `using = using or db_for_write(...)`
        # short-circuits on the already-truthy value - db_for_write is
        # never reached a second time at all.
        deferred = models.Post.objects.only("content").get(pk=self.post.pk)
        deferred.content = "# Router consistency"

        with patch("kioblog.models.router.db_for_write", return_value="default") as mocked_router:
            deferred.save()

        mocked_router.assert_called_once()

    def test_none_content_does_not_crash_the_cache_key(self) -> None:
        # render_markdown() already treats None as "" (md.convert(text or
        # "")) - the cache key needs to hash to the same thing, not raise
        # AttributeError on .encode() before ever reaching render_markdown.
        unsaved = models.Post(pk=999999, title="draft", content=None, user=self.user, category=self.category)
        self.assertEqual(unsaved.content_html, "")

    def test_second_read_on_the_same_instance_sees_a_later_in_memory_edit(self) -> None:
        # hasattr(self, "_rendered") alone only guards the *first* call - a
        # second content_html read on the SAME instance, after mutating
        # .content in between, used to keep returning the first render
        # regardless, since nothing rechecked whether .content had moved.
        post = models.Post.objects.get(pk=self.post.pk)
        first_html = post.content_html

        post.content = "# Changed after the first read"
        second_html = post.content_html

        self.assertNotEqual(first_html, second_html)
        self.assertIn("Changed after the first read", second_html)

    def test_renderer_version_bump_forces_a_fresh_render(self) -> None:
        # A kioblog release that changes render_markdown's output (the
        # code-block markup, Pygments styling, the toc settings, ...) isn't
        # reflected for a post nobody edited - the content hash alone has no
        # way to know the *code* that turns it into HTML changed underneath
        # it. Bumping _RENDER_CACHE_VERSION is how that gets forced.
        _ = models.Post.objects.get(pk=self.post.pk).content_html  # populate the cache under v1

        with patch("kioblog.models._RENDER_CACHE_VERSION", 2):
            with patch("kioblog.models.render_markdown", MagicMock(side_effect=render_markdown)) as mocked:
                _ = models.Post.objects.get(pk=self.post.pk).content_html
                self.assertEqual(mocked.call_count, 1)

    def test_cache_set_uses_a_bounded_timeout(self) -> None:
        # Every edit leaves a new cache key (it's a content hash), so a
        # timeout=None here would mean every past revision of every post
        # stays cached forever - fine for backends that cap their own size,
        # not guaranteed on a Redis cache without an eviction policy
        # configured (its default is to reject writes once full, not evict).
        with patch("kioblog.models.cache.set") as mocked_set:
            _ = models.Post.objects.get(pk=self.post.pk).content_html
        mocked_set.assert_called_once_with(ANY, ANY, timeout=models._RENDER_CACHE_TIMEOUT)
        self.assertIsNotNone(models._RENDER_CACHE_TIMEOUT)

    def test_unsaved_post_still_renders_without_touching_the_cache(self) -> None:
        # No pk yet, and `updated` isn't set until the first save() - a
        # downstream consumer previewing an unsaved Post must not crash.
        #
        # Patches cache.get/cache.set directly rather than only checking the
        # render is correct: the render alone would pass even if this path
        # wastefully called through to the cache, which the test's own name
        # promises it doesn't.
        unsaved = models.Post(title="draft", content="# Preview", user=self.user, category=self.category)
        self.assertIsNone(unsaved.pk)

        with patch("kioblog.models.cache.get") as mocked_get, patch("kioblog.models.cache.set") as mocked_set:
            self.assertIn("Preview", unsaved.content_html)

        mocked_get.assert_not_called()
        mocked_set.assert_not_called()

    def test_manually_assigned_pk_on_an_unsaved_post_never_touches_the_cache(self) -> None:
        # Copilot finding, real: `self.pk is None` alone doesn't mean
        # "unsaved" - a Post constructed with an explicit pk (as
        # test_manually_assigned_pk_on_an_unsaved_post_does_not_crash, above,
        # already covers for the crash case) has self.pk set but is still
        # unsaved (self._state.adding stays True until a real save()
        # completes). Without checking _state.adding too, this preview path
        # reached the shared cache under a real-looking database key -
        # caching content that was never actually persisted under that pk,
        # and violating the same "unsaved previews never touch the shared
        # cache" contract test_unsaved_post_still_renders_without_touching_
        # the_cache proves for the no-pk case just above.
        unsaved = models.Post(
            pk=999999, title="draft", content="# Manual pk preview", user=self.user, category=self.category
        )
        self.assertIsNotNone(unsaved.pk)
        self.assertTrue(unsaved._state.adding)

        with patch("kioblog.models.cache.get") as mocked_get, patch("kioblog.models.cache.set") as mocked_set:
            self.assertIn("Manual pk preview", unsaved.content_html)

        mocked_get.assert_not_called()
        mocked_set.assert_not_called()

    def test_cache_get_failure_falls_back_to_a_fresh_render(self) -> None:
        # Copilot finding, real: this cache only exists to skip re-rendering
        # - a backend outage (Redis/Memcached down, a transient network
        # error, ...) must not turn "post pages unavailable" into a side
        # effect of "cache unavailable". Nothing before this caught an
        # exception from cache.get(), so it would have propagated straight
        # out of content_html and 500'd the page.
        with patch("kioblog.models.cache.get", side_effect=ConnectionError("cache backend unreachable")):
            html = models.Post.objects.get(pk=self.post.pk).content_html
        self.assertTrue(html)

    def test_cache_set_failure_does_not_crash_the_render(self) -> None:
        # Same reasoning as the cache.get case above, for the write side:
        # render_markdown() has already succeeded by the time cache.set()
        # would run, so a write failure there must not discard that result.
        with patch("kioblog.models.cache.set", side_effect=ConnectionError("cache backend unreachable")):
            html = models.Post.objects.get(pk=self.post.pk).content_html
        self.assertTrue(html)
