"""Backfill Post.published from the legacy Post.created date.

Existing rows got published=timezone.now() when the field was added in 0004;
this copies their real created date (at midnight, timezone-aware) so ordering
and prev/next reflect the original publish order. New rows keep the default.
"""

import datetime

from django.db import migrations
from django.utils import timezone


def backfill_published(apps, schema_editor):
    Post = apps.get_model('kioblog', 'Post')
    for post in Post.objects.all():
        if not post.created:
            continue
        dt = datetime.datetime.combine(post.created, datetime.time.min)
        if settings_use_tz() and timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_default_timezone())
        post.published = dt
        post.save(update_fields=['published'])


def settings_use_tz():
    from django.conf import settings
    return getattr(settings, 'USE_TZ', False)


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0004_tag_post_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_published, migrations.RunPython.noop),
    ]
