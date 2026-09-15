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

That refusal check and the DeleteModel that follows it are not atomic
against a concurrent writer: `count()` takes no lock, so a row inserted by
another process between the check and the drop is deleted anyway despite
the check having passed. Not fixed with table/row locking here - the
locking syntax needed isn't portable across the backends this package
supports, for a guard that exists for a one-time, manually-triggered
migration. Run this the way any irreversible schema change should run: in
a maintenance window, with nothing else writing to Comment.
"""

from django.db import migrations


def refuse_if_comments_exist(apps, schema_editor):
    Comment = apps.get_model('kioblog', 'Comment')
    count = Comment.objects.using(schema_editor.connection.alias).count()
    if count:
        # Deliberately NOT "run dumpdata kioblog.Comment" or "delete via the
        # ORM from a shell": by the time an operator reads this, the kioblog
        # version they have INSTALLED is the one that removed Comment from
        # models.py/admin.py - the app registry no longer has it, so any
        # advice that goes through the ORM (dumpdata, `from kioblog.models
        # import Comment`) fails too. Only database-level guidance survives
        # that.
        raise RuntimeError(
            f"Refusing to migrate: {count} Comment row(s) still exist, and this "
            "migration deletes the Comment table entirely. This version of "
            "kioblog no longer has a Comment model for the ORM to reach - back "
            "the table up at the database level first, with your engine's own "
            "tool (pg_dump -t kioblog_comment, mysqldump <db> kioblog_comment, "
            "or a copy of the sqlite file), or inspect/export it directly via "
            "`python manage.py dbshell`. Once you've backed it up (or don't "
            "need it), delete the rows - DELETE FROM kioblog_comment; from "
            "that same dbshell - then re-run migrate."
        )
    # Copilot finding: the module docstring explains the TOCTOU race below
    # (count() isn't locked), but that warning was only ever visible to
    # someone who happened to read this file - not to whoever actually runs
    # `migrate` and watches it succeed. Printed here, on the path that's
    # about to drop the table, so the precondition this migration depends on
    # (nothing else writing to Comment) is stated at the moment it matters,
    # not just documented somewhere a successful run never surfaces.
    print(
        "    kioblog 0011_delete_comment: preflight check passed (0 Comment "
        "rows) - proceeding to drop the table. This check is not locked "
        "against a concurrent writer; if anything else could still be "
        "writing to Comment right now, stop and re-run this in a "
        "maintenance window instead."
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
