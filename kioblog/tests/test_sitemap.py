from xml.etree import ElementTree

from django.urls import reverse

from kioblog import models
from kioblog.tests import base

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapTests(base.BaseTestCase):
    """Assert the generated XML, not the class attributes.

    A `protocol = "https"` on the class is only half the story: the sitemap
    view always calls get_urls(protocol=request.scheme), and Sitemap.get_protocol
    is `self.protocol or protocol or <default>`. Because request.scheme is
    always truthy, that trailing default never applies here - a class without
    an explicit protocol silently inherits the scheme of whatever request
    happened to hit it. Checking `MainPageSitemap.protocol == "https"` would
    pass on a class that still emitted http:// in production, so these tests
    parse the response instead.

    The requests below are deliberately plain http (no secure=True). Sending
    them over https would make request.scheme "https" and every URL would come
    out https whether or not the class declares it, which is exactly the way
    this regression stayed invisible.
    """

    def setUp(self) -> None:
        super().setUp()
        self.tag = models.Tag.objects.create(title="django", slug="django")
        self.post.tags.add(self.tag)

    def _locations(self) -> list:
        response = self.client.get(reverse("django.contrib.sitemaps.views.sitemap"))
        self.assertEqual(response.status_code, 200)
        root = ElementTree.fromstring(response.content)
        locations = [node.text for node in root.findall("sm:url/sm:loc", SITEMAP_NS)]
        self.assertTrue(locations, "sitemap.xml rendered no <loc> entries at all")
        return locations

    def test_main_page_url_is_https(self) -> None:
        home = reverse("kioblog-home")
        matches = [loc for loc in self._locations() if loc.endswith(home)]

        self.assertEqual(len(matches), 1, f"expected exactly one entry for {home}")
        self.assertTrue(
            matches[0].startswith("https://"),
            f"main page is listed as {matches[0]}; the sitemap should advertise the https canonical URL",
        )

    def test_every_sitemap_url_is_https(self) -> None:
        # Guards all four Sitemap classes at once, so a new one added without
        # protocol = "https" fails here rather than quietly shipping http URLs.
        offenders = [loc for loc in self._locations() if not loc.startswith("https://")]
        self.assertEqual(offenders, [], f"these sitemap URLs are not https: {offenders}")

    def test_sitemap_covers_posts_categories_and_tags(self) -> None:
        # Pins down that the https assertion above is actually inspecting every
        # section. If a section stopped emitting entries the test would keep
        # passing on an empty set without this.
        locations = self._locations()
        expected = [
            reverse("kioblog-post", kwargs={"slug": self.post.slug}),
            reverse("kioblog-category", kwargs={"category": self.category.slug}),
            reverse("kioblog-tag", kwargs={"tag": self.tag.slug}),
            reverse("kioblog-home"),
        ]
        for path in expected:
            self.assertTrue(
                any(loc.endswith(path) for loc in locations),
                f"{path} is missing from sitemap.xml",
            )
