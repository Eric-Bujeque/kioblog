from kioblog import models


def kioblog_settings(request):
    return {
        'kioblog_settings': {meta.key: meta.value for meta in models.Meta.objects.all()},
    }


def kioblog_categories(request):
    return {
        'kioblog_categories': models.Category.objects.all(),
    }
