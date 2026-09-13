"""Give Category and Tag a default ordering (Post already had one - see
0004). Without it, django.contrib.sitemaps paginating either queryset
(CategorySitemap/TagSitemap in sitemap.py both do `.objects.all()`) trips
Django's own UnorderedObjectListWarning: pagination over an unordered
queryset can return duplicate or missing rows across pages if a write lands
between two page fetches. Below the sitemap's per-page cap (50,000 URLs)
this repo won't hit in practice, so no behaviour bug today - just the
warning, until it grows past that cap.

AlterModelOptions has no schema to migrate - `ordering` is Meta-only,
never a column - so this is pure migration-history bookkeeping.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kioblog', '0009_enforce_unique_category_slugs'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ['title'], 'verbose_name_plural': 'Categories'},
        ),
        migrations.AlterModelOptions(
            name='tag',
            options={'ordering': ['title']},
        ),
    ]
