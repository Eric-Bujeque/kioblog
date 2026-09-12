"""Post._render() caches Markdown+Pygments rendering across requests (via
django.core.cache), not just within one Python instance's lifetime the way it
always has. Each test re-fetches the post as a fresh instance to simulate
what actually happens across two HTTP requests - Post._rendered (the
per-instance cache) never survives that, only the cross-request one could.
"""

from unittest.mock import MagicMock, patch

from kioblog import models
from kioblog.markdown.render import render_markdown
from kioblog.tests import base


class RenderCacheTests(base.BaseTestCase):
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
        stale.save()  # bumps `updated` (auto_now), which the cache key includes

        fresh = models.Post.objects.get(pk=self.post.pk)
        self.assertIn("A brand new heading", fresh.content_html)
        self.assertNotIn(self.post.content, fresh.content_html)

    def test_unsaved_post_still_renders_without_touching_the_cache(self) -> None:
        # No pk yet, and `updated` isn't set until the first save() - a
        # downstream consumer previewing an unsaved Post must not crash.
        unsaved = models.Post(title="draft", content="# Preview", user=self.user, category=self.category)
        self.assertIsNone(unsaved.pk)
        self.assertIn("Preview", unsaved.content_html)
