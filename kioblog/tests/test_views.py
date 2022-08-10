import secrets

from django.urls import reverse

from kioblog import models
from kioblog.tests import base


class KioblogViews(base.BaseTestCase):
    def setUp(self) -> None:
        super(KioblogViews, self).setUp()
        [models.Post.objects.create(
            title=secrets.token_hex(nbytes=16),
            content=secrets.token_hex(nbytes=16),
            user=self.user,
            category=self.category2,
            slug=secrets.token_hex(nbytes=16)
        ) for n in range(9)]

    def test_home(self) -> None:
        response = self.client.get(reverse('kioblog-home'))
        must_keys = ['posts', 'page_range', 'recent_posts']
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all([key in list(response.context_data.keys()) for key in must_keys]))

    def test_categories(self) -> None:
        response = self.client.get(reverse('kioblog-category', kwargs={'category': self.category2.slug}))
        must_keys = ['posts', 'page_range', 'recent_posts']
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all([key in list(response.context_data.keys()) for key in must_keys]))
        self.assertEqual(response.context_data['posts'].paginator.count, 9)
        self.assertNotIn(self.post, response.context_data['posts'].paginator.object_list)

    def test_pages(self) -> None:
        response = self.client.get(reverse('kioblog-page', kwargs={'page': 1}))
        must_keys = ['posts', 'page_range', 'recent_posts']
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all([key in list(response.context_data.keys()) for key in must_keys]))
        self.assertEqual(len(response.context_data['posts'].object_list), 5)
        self.assertNotIn(self.post, response.context_data['posts'].object_list)
        self.assertIn(self.post, response.context_data['posts'].paginator.object_list)

    def test_post(self) -> None:
        response = self.client.get(reverse('kioblog-post', kwargs={'slug': self.post.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['post'], self.post)
        self.assertIn(self.post.content, response.content.decode())
