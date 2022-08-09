from django.test import TestCase

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
