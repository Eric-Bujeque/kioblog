"""Retrofit `unique=True` onto Category.slug - same shape as 0007 for
Post.slug, reusing the same deduplicate_slugs helper.

Category was kioblog.tests.test_slugs's fixture for unit-testing that helper
in isolation, specifically because it was the one slugged model still
unconstrained - this migration removes that, so there is no longer a model
the ORM will let collide outside a reversed migration state. That file is
gone; the same scenarios (including the "don't rename onto an already-taken
slug" case that caught a real bug in the helper before it shipped) now live
in kioblog.tests.test_migrations, exercised against this migration directly.

Doesn't 500 the way a duplicate Post.slug does, but it's still wrong two
different ways. HomeView resolves a URL's slug via
Category.objects.filter(slug=...).first(), so a category page can silently
render a *different* category than the one its own URL names. sitemap.py's
CategorySitemap enumerates every Category row directly (no .filter().first()
at all) and builds each URL from its own slug, so duplicates instead make it
emit the *same* <loc> more than once.
"""

from django.db import migrations, models

from kioblog.slugs import deduplicate_slugs


def deduplicate_category_slugs(apps, schema_editor):
    Category = apps.get_model('kioblog', 'Category')
    # Without `using`, this reads and writes the "default" database alias
    # regardless of which connection `migrate` is actually targeting - same
    # gap 0007 had for Post, fixed there the same way.
    deduplicate_slugs(Category, using=schema_editor.connection.alias)


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
