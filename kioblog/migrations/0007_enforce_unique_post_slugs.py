"""Retrofit `unique=True` onto Post.slug.

PostView resolves posts by slug alone (DetailView.get_object filters on it
and calls .get()), and nothing before this migration stopped two posts from
sharing one - the admin's prepopulated_fields only *suggests* a slug, it
never enforces uniqueness. A duplicate makes .get() raise
MultipleObjectsReturned, which DetailView does not catch, so the post page
500s instead of serving either post.

An existing installation may already have duplicates sitting in its
database, so the AlterField is preceded by a data migration that renames
collisions (kioblog.slugs.deduplicate_slugs) rather than letting `migrate`
fail on someone else's data.
"""

from django.conf import settings
from django.db import migrations, models

from kioblog.slugs import deduplicate_slugs


def deduplicate_post_slugs(apps, schema_editor):
    Post = apps.get_model('kioblog', 'Post')
    # Without `using`, the historical model's default manager always reads
    # and writes the "default" database alias, regardless of which
    # connection `migrate` is actually targeting - Django's own migration
    # docs call this out explicitly for RunPython operations.
    #
    # fold=True only on MySQL by default: Post.slug is public (every post
    # URL is /<slug>/), so case/accent-folding on a case-sensitive backend
    # (SQLite, PostgreSQL's defaults) would silently rename a live, distinct,
    # already-working slug like "Foo" for no reason - the real unique index
    # on those backends would have accepted it unchanged. Folding is only
    # actually needed on a backend whose default collation is itself
    # permissive - a vendor-level guess, not the column's actual collation;
    # see deduplicate_slugs's own `fold` docstring for what that does and
    # doesn't cover.
    #
    # KIOBLOG_SLUG_FOLD lets an installation override that guess: unset
    # (None, the default), this falls back to the vendor heuristic above.
    # Set it to True or False in settings.py before running this migration
    # to force folding either way - the escape hatch for anyone on a MySQL
    # collation that isn't the permissive default (utf8mb4_bin, e.g.), where
    # the vendor-only guess would fold unnecessarily.
    fold = getattr(settings, 'KIOBLOG_SLUG_FOLD', None)
    if fold is None:
        fold = schema_editor.connection.vendor == 'mysql'
    deduplicate_slugs(Post, using=schema_editor.connection.alias, fold=fold)


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0006_post_content_markdownx'),
    ]

    operations = [
        migrations.RunPython(deduplicate_post_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='post',
            name='slug',
            field=models.SlugField(max_length=200, unique=True),
        ),
    ]
