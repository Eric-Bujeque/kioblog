from django.test import TestCase
from django.contrib.auth.models import User

from kioblog import models


class BaseTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username='testuser')
        self.category = models.Category.objects.create(title='test', slug='test')
        self.category2 = models.Category.objects.create(title='test2', slug='test2')
        self.post = models.Post.objects.create(
            title='test title',
            content='Foo Bar',
            user=self.user,
            category=self.category,
            slug='testtitle'
        )
