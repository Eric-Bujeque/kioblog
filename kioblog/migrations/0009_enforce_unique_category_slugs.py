"""Retrofit `unique=True` onto Category.slug - same shape as 0007 for
Post.slug, reusing the same deduplicate_slugs helper.

Category was kioblog.tests.test_slugs's fixture for unit-testing that helper
in isolation, specifically because it was the one slugged model still
unconstrained - this migration removes that, so there is no longer a model
the ORM will let collide outside a reversed migration state. That file is
gone; the same scenarios (including the "don't rename onto an already-taken
slug" case that caught a real bug in the helper before it shipped) now live
in kioblog.tests.test_migrations, exercised against this migration directly.

HomeView and sitemap.py both resolve a category by
Category.objects.filter(slug=...).first(), so a duplicate here doesn't 500
the way a duplicate Post.slug does - it silently picks one of the matches
arbitrarily. Still worth fixing: the sitemap's URL for a category can end up
routing to a *different* category than the one it was generated from.
"""

from django.db import migrations, models

from kioblog.slugs import deduplicate_slugs


def deduplicate_category_slugs(apps, schema_editor):
    Category = apps.get_model('kioblog', 'Category')
    deduplicate_slugs(Category)


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0008_post_updated'),
    ]

    operations = [
        migrations.RunPython(deduplicate_category_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(max_length=200, unique=True),
        ),
    ]
