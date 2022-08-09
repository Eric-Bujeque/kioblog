from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from kioblog import models


class CategorySitemap(Sitemap):
    changefreq = "never"
    priority = 0.5
    protocol = 'https'

    def items(self):
        return models.Category.objects.all()

    def location(self, obj):
        return reverse('kioblog-category', kwargs={'category': obj.slug})


class PostSitemap(Sitemap):
    changefreq = "never"
    priority = 0.6
    protocol = 'https'

    def items(self):
        return models.Post.objects.all()

    def location(self, obj):
        return reverse('kioblog-post', kwargs={'slug': obj.slug})


class MainPageSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return ['kioblog-home']

    def location(self, item):
        return reverse(item)
