from django.db.models import Count, Q

from kioblog import models


def kioblog_settings(request):
    return {
        "kioblog_settings": {meta.key: meta.value for meta in models.Meta.objects.all()},
    }


def kioblog_categories(request):
    return {
        "kioblog_categories": models.Category.objects.annotate(post_count=Count("post", filter=Q(post__draft=False))),
    }
