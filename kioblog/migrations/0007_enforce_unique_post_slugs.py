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

from django.db import migrations, models

from kioblog.slugs import deduplicate_slugs


def deduplicate_post_slugs(apps, schema_editor):
    Post = apps.get_model('kioblog', 'Post')
    # Without `using`, the historical model's default manager always reads
    # and writes the "default" database alias, regardless of which
    # connection `migrate` is actually targeting - Django's own migration
    # docs call this out explicitly for RunPython operations.
    deduplicate_slugs(Post, using=schema_editor.connection.alias)


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
