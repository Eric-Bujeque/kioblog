from django.urls import reverse

from kioblog import models
from kioblog.tests import base


class PostFeedTests(base.BaseTestCase):
    def test_feed_lists_published_posts(self) -> None:
        response = self.client.get(reverse("kioblog-feed"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/rss+xml; charset=utf-8")

        content = response.content.decode()
        self.assertIn(f"<title>{self.post.title}</title>", content)
        self.assertIn(reverse("kioblog-post", kwargs={"slug": self.post.slug}), content)

    def test_feed_excludes_drafts(self) -> None:
        draft = models.Post.objects.create(
            title="secret draft",
            content="x",
            user=self.user,
            category=self.category,
            slug="secret-draft",
            draft=True,
        )
        response = self.client.get(reverse("kioblog-feed"))
        self.assertNotIn(draft.title, response.content.decode())

    def test_feed_title_and_description_follow_meta_settings(self) -> None:
        # blog_title/meta_description are seeded by migration 0002 (get_or_create),
        # so every install already has a row - editing it in place, the way the
        # admin does, not creating a second one with the same key.
        models.Meta.objects.filter(key="blog_title").update(value="My Blog")
        models.Meta.objects.filter(key="meta_description").update(value="Posts about things.")

        content = self.client.get(reverse("kioblog-feed")).content.decode()
        self.assertIn("<title>My Blog</title>", content)
        self.assertIn("Posts about things.", content)
