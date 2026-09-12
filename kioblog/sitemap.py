from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from kioblog import models


class CategorySitemap(Sitemap):
    changefreq = "never"
    priority = 0.5
    protocol = "https"

    def items(self):
        return models.Category.objects.all()

    def location(self, obj):
        return reverse("kioblog-category", kwargs={"category": obj.slug})


class PostSitemap(Sitemap):
    changefreq = "never"
    priority = 0.6
    protocol = "https"

    def items(self):
        return models.Post.objects.filter(draft=False)

    def lastmod(self, obj):
        # `updated` (auto_now), not `published`: lastmod is supposed to say
        # when the content last changed, and `published` never moves again
        # once a post is edited after going live.
        return obj.updated

    def location(self, obj):
        return reverse("kioblog-post", kwargs={"slug": obj.slug})


class TagSitemap(Sitemap):
    changefreq = "never"
    priority = 0.4
    protocol = "https"

    def items(self):
        return models.Tag.objects.all()

    def location(self, obj):
        return reverse("kioblog-tag", kwargs={"tag": obj.slug})


class MainPageSitemap(Sitemap):
    priority = 0.5
    changefreq = "daily"
    protocol = "https"

    def items(self):
        return ["kioblog-home"]

    def location(self, item):
        return reverse(item)
