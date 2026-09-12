import json

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

    def test_json_ld_is_valid_and_matches_the_post(self) -> None:
        self.post.excerpt = "A summary."
        data = json.loads(self.post.json_ld)
        self.assertEqual(data["@type"], "BlogPosting")
        self.assertEqual(data["headline"], self.post.title)
        self.assertEqual(data["description"], "A summary.")
        # DjangoJSONEncoder's datetime format (millisecond precision, "Z" for
        # UTC) isn't the same string as datetime.isoformat() - compare on the
        # to-the-second prefix both share rather than assume an exact format.
        self.assertEqual(data["datePublished"][:19], self.post.published.strftime("%Y-%m-%dT%H:%M:%S"))

    def test_json_ld_falls_back_to_username_without_a_full_name(self) -> None:
        # BaseTestCase's user has no first/last name - get_full_name() would
        # otherwise render an empty author.name.
        data = json.loads(self.post.json_ld)
        self.assertEqual(data["author"]["name"], self.user.username)

    def test_json_ld_omits_image_when_the_post_has_none(self) -> None:
        data = json.loads(self.post.json_ld)
        self.assertNotIn("image", data)

    def test_json_ld_escapes_a_script_close_tag_so_it_cant_break_out(self) -> None:
        # json.dumps alone would emit a literal "</script>" here, which HTML
        # parses as the end of the <script> tag post.html embeds this in -
        # everything after it would render as plain page text, not JSON-LD.
        self.post.title = "</script><script>alert(1)</script>"
        raw = self.post.json_ld
        self.assertNotIn("</script>", raw)
        # Still valid, and still carries the real title once decoded.
        data = json.loads(raw)
        self.assertEqual(data["headline"], self.post.title)

    def test_category_post_count_ignores_drafts(self) -> None:
        models.Post.objects.create(
            title="draft", content="x", user=self.user, category=self.category, slug="draft", draft=True
        )
        # self.post (non-draft) counts, the draft does not.
        self.assertEqual(self.category.post_count(), 1)
