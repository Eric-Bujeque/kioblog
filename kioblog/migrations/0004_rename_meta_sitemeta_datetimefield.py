# Generated manually — renames Meta→SiteMeta and upgrades DateField→DateTimeField.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0003_auto_20220809_1735'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Meta',
            new_name='SiteMeta',
        ),
        migrations.AlterField(
            model_name='post',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='comment',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
