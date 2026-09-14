"""Comment (created in 0001, never touched since) had no view, URL, form or
template anywhere in this codebase - a fully modeled feature nobody could
actually use. Removing it rather than leaving an unreachable table and admin
registration around; it can come back properly built (form, moderation,
threaded template) if that is ever actually wanted.

Nothing in kioblog's own code references it: grepped the whole package
before writing this and the only other hit was Pygments' own `Comment`
token type in pygments_onedark.py, unrelated. But that only proves nothing
kioblog *ships* writes to it - Comment was registered in the admin
(admin.py, until this PR), which lets any staff user create rows through
Django's generic CRUD with no public form involved at all. An existing
installation's database is not something this migration can see, so it
refuses to run if it isn't actually empty rather than assuming it is.
"""

from django.db import migrations


def refuse_if_comments_exist(apps, schema_editor):
    Comment = apps.get_model('kioblog', 'Comment')
    count = Comment.objects.using(schema_editor.connection.alias).count()
    if count:
        raise RuntimeError(
            f"Refusing to migrate: {count} Comment row(s) still exist, and this "
            "migration deletes the Comment table entirely. Back them up first, "
            "e.g.:\n"
            "  python manage.py dumpdata kioblog.Comment > comments_backup.json\n"
            "then re-run migrate. To proceed anyway and discard them, delete the "
            "rows first (Comment.objects.all().delete() from a shell)."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0010_category_tag_default_ordering'),
    ]

    operations = [
        migrations.RunPython(refuse_if_comments_exist, migrations.RunPython.noop),
        migrations.DeleteModel(
            name='Comment',
        ),
    ]
