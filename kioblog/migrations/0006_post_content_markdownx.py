from django.db import migrations
import markdownx.models


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0005_backfill_published'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='content',
            field=markdownx.models.MarkdownxField(),
        ),
    ]
