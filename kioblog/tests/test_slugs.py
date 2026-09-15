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

        # fold=True explicitly: this test is specifically about proving
        # folding works, so it shouldn't lean on whatever the function's own
        # default happens to be (deliberately the safe, non-destructive
        # fold=False, for any caller that forgets to choose).
        deduplicate_slugs(models.Category, fold=True)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.slug, "Foo")
        self.assertEqual(second.slug, "foo-2")

    def test_treats_accent_variants_as_colliding(self) -> None:
        # Same reasoning as the case-variant test above, for accents instead
        # of case: MySQL's accent-insensitive collations (the `*_ai_ci`
        # family) treat "café" and "cafe" as the same value for a unique
        # index, even though SQLite - case-sensitive by default too - lets
        # both coexist here without even reaching this function.
        first = models.Category.objects.create(title="one", slug="café")
        second = models.Category.objects.create(title="two", slug="cafe")

        deduplicate_slugs(models.Category, fold=True)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.slug, "café")
        self.assertEqual(second.slug, "cafe-2")

    def test_fold_false_leaves_case_and_accent_variants_untouched(self) -> None:
        # Post.slug is public - every post URL is /<slug>/ - so folding is
        # NOT free to apply unconditionally. On a case-sensitive backend
        # (SQLite, PostgreSQL's defaults), "Foo" and "foo" are genuinely
        # distinct values the real unique index would accept both of
        # unchanged; renaming one anyway would silently turn a live, working
        # URL into a 404 for no reason. Callers pass fold=False for those
        # backends (see migration 0007's own fold=... call).
        foo = models.Category.objects.create(title="one", slug="Foo")
        foo2 = models.Category.objects.create(title="two", slug="foo")
        cafe_accented = models.Category.objects.create(title="three", slug="café")
        cafe_plain = models.Category.objects.create(title="four", slug="cafe")

        deduplicate_slugs(models.Category, fold=False)

        foo.refresh_from_db()
        foo2.refresh_from_db()
        cafe_accented.refresh_from_db()
        cafe_plain.refresh_from_db()
        self.assertEqual(foo.slug, "Foo")
        self.assertEqual(foo2.slug, "foo")
        self.assertEqual(cafe_accented.slug, "café")
        self.assertEqual(cafe_plain.slug, "cafe")

    def test_default_is_fold_false_the_safe_non_destructive_choice(self) -> None:
        # Copilot finding, real: fold defaulted to True, which is backwards -
        # a default should be the safe choice, not the one that can rename a
        # live, working URL for no reason on a backend that never needed it.
        # Every actual call site in this codebase already passes fold=
        # explicitly (the migrations, from the connection's vendor; the two
        # tests above, deliberately, to prove folding itself works) - this
        # proves the *default* itself, with no fold= argument at all, in
        # case a future caller forgets to choose.
        foo = models.Category.objects.create(title="one", slug="Foo")
        foo2 = models.Category.objects.create(title="two", slug="foo")

        deduplicate_slugs(models.Category)

        foo.refresh_from_db()
        foo2.refresh_from_db()
        self.assertEqual(foo.slug, "Foo")
        self.assertEqual(foo2.slug, "foo")

    def test_using_is_threaded_to_the_manager_and_save(self) -> None:
        # A true cross-database check needs a second configured alias with
        # its own test database, which this repo's dev settings don't set up
        # - this instead proves the wiring itself: `using` reaches both the
        # query and the write, which is what actually fixes reading/writing
        # the "default" alias regardless of which connection is migrating.
        #
        # Two rows sharing a slug, not an empty queryset: an empty one never
        # reaches obj.save() at all, so it could only prove `using` reaches
        # the *read* - a regression that dropped `using=using` from the
        # write would still have passed this test.
        first = MagicMock(slug="dup")
        second = MagicMock(slug="dup")
        fake_model = MagicMock()
        fake_model.objects.using.return_value.only.return_value.order_by.return_value = [first, second]
        fake_model._meta.get_field.return_value.max_length = 200

        deduplicate_slugs(fake_model, using="replica")

        fake_model.objects.using.assert_called_once_with("replica")
        second.save.assert_called_once_with(using="replica", update_fields=["slug"])

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
