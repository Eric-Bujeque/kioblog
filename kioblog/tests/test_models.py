from django.utils import timezone

from kioblog.tests import base
from kioblog import models


class KioblogModels(base.BaseTestCase):
    def test_post_first_paragraph(self) -> None:
        first_paragraph = '<p>first paragraph</p>'
        self.post.content = '{}<p>Second</p>'.format(first_paragraph)
        self.assertEqual(self.post.first_paragraph(), first_paragraph)

    def test_post_get_recent_posts_no_current(self) -> None:
        self.assertIn(self.post, models.Post.get_recent_posts())

    def test_post_get_recent_posts_current(self) -> None:
        self.assertNotIn(self.post, models.Post.get_recent_posts(self.post.slug))

    def test_content_html_renders_markdown(self) -> None:
        self.post.content = '# Heading\n\nBody text.'
        self.assertIn('<h2 id="heading">Heading</h2>', self.post.content_html)
        self.assertIn('<p>Body text.</p>', self.post.content_html)

    def test_reading_time_at_least_one_minute(self) -> None:
        self.assertGreaterEqual(self.post.reading_time, 1)

    def test_get_previous_and_next_are_nearest_neighbours(self) -> None:
        now = timezone.now()
        older = models.Post.objects.create(
            title='older', content='x', user=self.user, category=self.category,
            slug='older', published=now - timezone.timedelta(days=2))
        newer = models.Post.objects.create(
            title='newer', content='x', user=self.user, category=self.category,
            slug='newer', published=now + timezone.timedelta(days=2))
        self.assertEqual(self.post.get_previous(), older)
        self.assertEqual(self.post.get_next(), newer)

    def test_display_excerpt_prefers_explicit_excerpt(self) -> None:
        self.post.excerpt = 'A hand-written summary.'
        self.post.content = '# Heading\n\nRendered paragraph text.'
        self.assertEqual(self.post.display_excerpt, 'A hand-written summary.')

    def test_display_excerpt_falls_back_to_rendered_content(self) -> None:
        self.post.excerpt = ''
        self.post.content = '# Heading\n\nRendered paragraph text.'
        self.assertEqual(self.post.display_excerpt, 'Rendered paragraph text.')

    def test_get_previous_and_next_break_ties_on_same_published(self) -> None:
        same_time = timezone.now()
        p1 = models.Post.objects.create(
            title='tie-1', content='x', user=self.user, category=self.category,
            slug='tie-1', published=same_time)
        p2 = models.Post.objects.create(
            title='tie-2', content='x', user=self.user, category=self.category,
            slug='tie-2', published=same_time)
        p3 = models.Post.objects.create(
            title='tie-3', content='x', user=self.user, category=self.category,
            slug='tie-3', published=same_time)
        # Same published (e.g. midnight-backfilled posts); ordering falls back to id.
        self.assertEqual(p2.get_previous(), p1)
        self.assertEqual(p2.get_next(), p3)

    def test_related_posts_share_category_and_exclude_self(self) -> None:
        sibling = models.Post.objects.create(
            title='sibling', content='x', user=self.user, category=self.category,
            slug='sibling')
        related = self.post.related_posts()
        self.assertIn(sibling, related)
        self.assertNotIn(self.post, related)

    def test_category_post_count_ignores_drafts(self) -> None:
        models.Post.objects.create(
            title='draft', content='x', user=self.user, category=self.category,
            slug='draft', draft=True)
        # self.post (non-draft) counts, the draft does not.
        self.assertEqual(self.category.post_count(), 1)
