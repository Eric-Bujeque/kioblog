"""Unit-level check of kioblog.slugs.deduplicate_slugs in isolation.

Runs it against Category, the one model in this codebase still built without
a unique slug at this point - not because this is really about categories,
but because it needs a real model whose slug the ORM will let collide.
migration 0007 exercises the same function against Post's actual migration
history in test_migrations.py; this just isolates the renaming algorithm.
"""

from unittest.mock import MagicMock

from kioblog import models
from kioblog.slugs import deduplicate_slugs
from kioblog.tests import base


class DeduplicateSlugsTests(base.BaseTestCase):
    def test_treats_case_variants_as_colliding(self) -> None:
        # SQLite's default collation is case-sensitive, so "Foo"/"foo" can
        # coexist here without even reaching this function - but a
        # case-insensitive collation (MySQL's default, for one) would treat
        # them as the same value for a unique index. Matching that
        # pessimistically means the AlterField that follows this migration
        # doesn't fail on installations using such a database.
        first = models.Category.objects.create(title="one", slug="Foo")
        second = models.Category.objects.create(title="two", slug="foo")

        deduplicate_slugs(models.Category)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.slug, "Foo")
        self.assertEqual(second.slug, "foo-2")

    def test_using_is_threaded_to_the_manager_and_save(self) -> None:
        # A true cross-database check needs a second configured alias with
        # its own test database, which this repo's dev settings don't set up
        # - this instead proves the wiring itself: `using` reaches both the
        # query and the write, which is what actually fixes reading/writing
        # the "default" alias regardless of which connection is migrating.
        fake_model = MagicMock()
        fake_model.objects.using.return_value.order_by.return_value = []
        fake_model._meta.get_field.return_value.max_length = 200

        deduplicate_slugs(fake_model, using="replica")

        fake_model.objects.using.assert_called_once_with("replica")

    def test_keeps_the_first_row_and_renames_the_rest(self) -> None:
        first = models.Category.objects.create(title="one", slug="cat")
        second = models.Category.objects.create(title="two", slug="cat")
        third = models.Category.objects.create(title="three", slug="cat")

        deduplicate_slugs(models.Category)

        first.refresh_from_db()
        second.refresh_from_db()
        third.refresh_from_db()
        self.assertEqual(first.slug, "cat")
        self.assertEqual(second.slug, "cat-2")
        self.assertEqual(third.slug, "cat-3")

    def test_leaves_distinct_slugs_untouched(self) -> None:
        a = models.Category.objects.create(title="a", slug="a")
        b = models.Category.objects.create(title="b", slug="b")

        deduplicate_slugs(models.Category)

        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.slug, "a")
        self.assertEqual(b.slug, "b")

    def test_never_renames_onto_an_already_taken_slug(self) -> None:
        # "cat" collides and would naturally be renamed to "cat-2" - except
        # "cat-2" is already someone else's real slug. The rename must skip
        # past it rather than create a second collision.
        first = models.Category.objects.create(title="one", slug="cat")
        second = models.Category.objects.create(title="two", slug="cat")
        taken = models.Category.objects.create(title="taken", slug="cat-2")

        deduplicate_slugs(models.Category)

        first.refresh_from_db()
        second.refresh_from_db()
        taken.refresh_from_db()
        self.assertEqual(first.slug, "cat")
        self.assertEqual(taken.slug, "cat-2")
        self.assertEqual(second.slug, "cat-3")

    def test_truncates_to_stay_within_max_length(self) -> None:
        max_length = models.Category._meta.get_field("slug").max_length
        long_slug = "x" * max_length
        first = models.Category.objects.create(title="one", slug=long_slug)
        second = models.Category.objects.create(title="two", slug=long_slug)

        deduplicate_slugs(models.Category)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.slug, long_slug)
        self.assertEqual(second.slug, f"{'x' * (max_length - 2)}-2")
        self.assertLessEqual(len(second.slug), max_length)
