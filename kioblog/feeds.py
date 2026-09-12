from django.contrib.syndication.views import Feed
from django.urls import reverse

from kioblog import models


def _meta(key, default=""):
    # Same source as the kioblog_settings context processor - the Meta
    # key/value model consumers already edit in the admin - so the feed's
    # title/description follow whatever they've set there without a second
    # place to configure it.
    return models.Meta.objects.filter(key=key).values_list("value", flat=True).first() or default


class PostFeed(Feed):
    def title(self):
        return _meta("blog_title", "Blog")

    def link(self):
        return reverse("kioblog-home")

    def description(self):
        return _meta("meta_description")

    def items(self):
        # Post.Meta.ordering (-published, -id) applies here too, so this is
        # already newest-first without an explicit order_by.
        return models.Post.objects.filter(draft=False)[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.display_excerpt

    def item_link(self, item):
        return reverse("kioblog-post", kwargs={"slug": item.slug})

    def item_pubdate(self, item):
        return item.published
