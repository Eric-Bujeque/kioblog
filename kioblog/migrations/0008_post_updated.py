from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0007_enforce_unique_post_slugs'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='updated',
            # auto_now backfills every existing row with a one-off default at
            # migration time - django.utils.timezone.now here, same as it is
            # for `published` in 0004. From the next save() on, auto_now takes
            # over and this default is never consulted again.
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            # Without this, the default above gets baked into the ongoing
            # migration *state* even though the model has none (only
            # auto_now=True) - confirmed with `makemigrations --check
            # --dry-run`, which then proposes a no-op AlterField purely to
            # reconcile that phantom default away.
            preserve_default=False,
        ),
    ]
