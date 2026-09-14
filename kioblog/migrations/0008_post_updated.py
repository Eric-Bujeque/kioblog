from django.db import migrations, models
import django.utils.timezone


def backfill_updated_from_published(apps, schema_editor):
    # The AddField above already put a value in every existing row (it has
    # to - the column is NOT NULL) - timezone.now(), evaluated once at
    # migration time. Left there, every pre-existing post would suddenly
    # report "updated today" the moment this migration runs, which is
    # exactly what this field exists to NOT do: PostSitemap.lastmod (see
    # sitemap.py) would advertise the deploy date for every unchanged post,
    # likely triggering a one-time mass recrawl. `published` is the closest
    # thing to a real "last known state" timestamp already on these rows -
    # it's also what lastmod already pointed at before this migration, so
    # this backfill is a no-op for lastmod's *output*, not just a improvement.
    Post = apps.get_model('kioblog', 'Post')
    Post.objects.using(schema_editor.connection.alias).update(updated=models.F('published'))


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0007_enforce_unique_post_slugs'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='updated',
            # auto_now backfills every existing row with a one-off default at
            # migration time - django.utils.timezone.now here, same shape as
            # `published` in 0004. From the next save() on, auto_now takes
            # over and this default is never consulted again. The RunPython
            # below immediately overwrites it with something more meaningful
            # for existing rows.
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            # Without this, the default above gets baked into the ongoing
            # migration *state* even though the model has none (only
            # auto_now=True) - confirmed with `makemigrations --check
            # --dry-run`, which then proposes a no-op AlterField purely to
            # reconcile that phantom default away.
            preserve_default=False,
        ),
        migrations.RunPython(backfill_updated_from_published, migrations.RunPython.noop),
    ]
