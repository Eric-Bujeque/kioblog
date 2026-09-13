"""Comment (created in 0001, never touched since) had no view, URL, form or
template anywhere in this codebase - a fully modeled feature nobody could
actually use. Removing it rather than leaving an unreachable table and admin
registration around; it can come back properly built (form, moderation,
threaded template) if that is ever actually wanted.

Nothing references it: grepped the whole package for `Comment` before
writing this and the only other hit was Pygments' own `Comment` token type
in pygments_onedark.py, unrelated.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0010_category_tag_default_ordering'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Comment',
        ),
    ]
