import datetime

from kioblog.tests import base
from kioblog import models


class KioblogModels(base.BaseTestCase):
    def test_post_first_paragraph(self) -> None:
        first_paragraph = '<p>first paragraph</p>'
        self.post.content = '{}<p>Second</p>'.format(first_paragraph)
        self.assertEqual(self.post.first_paragraph(), first_paragraph)

    def test_post_first_paragraph_empty(self) -> None:
        self.post.content = 'no html here'
        self.assertEqual(self.post.first_paragraph(), '')

    def test_post_get_recent_posts_no_current(self) -> None:
        self.assertIn(self.post, models.Post.get_recent_posts())

    def test_post_get_recent_posts_current(self) -> None:
        self.assertNotIn(self.post, models.Post.get_recent_posts(self.post.slug))

    def test_post_get_recent_posts_excludes_blocked(self) -> None:
        self.post.blocked = True
        self.post.save()
        self.assertNotIn(self.post, models.Post.get_recent_posts())

    def test_post_get_recent_posts_excludes_draft(self) -> None:
        self.post.draft = True
        self.post.save()
        self.assertNotIn(self.post, models.Post.get_recent_posts())

    def test_post_created_is_datetime(self) -> None:
        self.assertIsInstance(self.post.created, datetime.datetime)

    def test_comment_created_is_datetime(self) -> None:
        comment = models.Comment.objects.create(
            username='tester',
            content='hello',
            post=self.post,
            email='tester@example.com',
        )
        self.assertIsInstance(comment.created, datetime.datetime)

    def test_sitemeta_str(self) -> None:
        meta = models.SiteMeta.objects.create(key='test_key', value='test_value')
        self.assertEqual(str(meta), 'test_key')

    def test_sitemeta_create_and_query(self) -> None:
        models.SiteMeta.objects.create(key='custom_unique_key', value='My Blog')
        self.assertEqual(models.SiteMeta.objects.get(key='custom_unique_key').value, 'My Blog')
