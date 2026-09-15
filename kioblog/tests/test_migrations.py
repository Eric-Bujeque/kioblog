"""Proves migrations 0007 and 0009 are safe to run against a database that
already has duplicate Post/Category slugs - the exact situation an existing
installation upgrading past them is in, and the one a plain
`AlterField(unique=True)` would fail on.

Builds real duplicate rows against the pre-migration schema (which has no
constraint to stop them), then migrates forward and asserts every row
survives with a unique slug. This exercises the actual migrations, not a
reimplementation of them.

The Category tests below also carry deduplicate_slugs's edge-case coverage
(an already-taken target slug, truncation to stay within max_length) that
used to live in a standalone test_slugs.py, unit-testing the helper against
Category as a convenient fixture - "convenient" specifically because it was
the one slugged model still unconstrained. Migration 0009 removes that, so
there is no longer any model the ORM will let collide outside a reversed
migration state like this one.
"""

import importlib
from unittest.mock import MagicMock

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone

from kioblog.slugs import deduplicate_slugs


class DeduplicatePostSlugsMigrationTests(TransactionTestCase):
    # A plain TestCase wraps each test in one atomic transaction; reversing a
    # migration needs to toggle SQLite's foreign_keys pragma, which SQLite
    # refuses to do mid-transaction. TransactionTestCase runs without that
    # wrapper (resetting the database by truncation between tests instead).
    migrate_from = ("kioblog", "0006_post_content_markdownx")
    migrate_to = ("kioblog", "0007_enforce_unique_post_slugs")

    def setUp(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])

        old_apps = executor.loader.project_state([self.migrate_from]).apps
        User = old_apps.get_model("auth", "User")
        Category = old_apps.get_model("kioblog", "Category")
        Post = old_apps.get_model("kioblog", "Post")

        user = User.objects.create(username="migrationtestuser")
        category = Category.objects.create(title="cat", slug="cat")
        # Three posts already sharing a slug, plus an unrelated one that must
        # be left alone - all only possible because 0006 has no constraint.
        self.first = Post.objects.create(title="A", content="x", user=user, category=category, slug="dup")
        self.second = Post.objects.create(title="B", content="x", user=user, category=category, slug="dup")
        self.third = Post.objects.create(title="C", content="x", user=user, category=category, slug="dup")
        self.unrelated = Post.objects.create(title="D", content="x", user=user, category=category, slug="fine")
        # Case variants that must survive untouched: this test suite runs on
        # SQLite, a case-sensitive backend, so the migration's own
        # fold=(vendor == "mysql") should resolve to False here and leave
        # both alone - the real unique index accepts them both as-is.
        self.case_first = Post.objects.create(title="E", content="x", user=user, category=category, slug="Foo")
        self.case_second = Post.objects.create(title="F", content="x", user=user, category=category, slug="foo")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([self.migrate_to])
        self.new_apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        # Leave the test database on the newest migration for every other
        # test in the suite, regardless of how this one finishes.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_collisions_are_renamed_keeping_the_first_by_id(self) -> None:
        Post = self.new_apps.get_model("kioblog", "Post")
        self.assertEqual(Post.objects.get(pk=self.first.pk).slug, "dup")
        self.assertEqual(Post.objects.get(pk=self.second.pk).slug, "dup-2")
        self.assertEqual(Post.objects.get(pk=self.third.pk).slug, "dup-3")

    def test_unrelated_slug_is_untouched(self) -> None:
        Post = self.new_apps.get_model("kioblog", "Post")
        self.assertEqual(Post.objects.get(pk=self.unrelated.pk).slug, "fine")

    def test_every_row_survives_with_a_distinct_slug(self) -> None:
        Post = self.new_apps.get_model("kioblog", "Post")
        slugs = list(Post.objects.values_list("slug", flat=True))
        self.assertEqual(len(slugs), 6)
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_case_variants_are_left_alone_on_a_case_sensitive_backend(self) -> None:
        # The migration's own vendor check, not a passed-in flag, is what
        # decides fold here - this test's real connection is SQLite, so it
        # should resolve to False and leave both alone.
        Post = self.new_apps.get_model("kioblog", "Post")
        self.assertEqual(Post.objects.get(pk=self.case_first.pk).slug, "Foo")
        self.assertEqual(Post.objects.get(pk=self.case_second.pk).slug, "foo")


class PostSlugFoldSettingOverrideMigrationTests(TransactionTestCase):
    # Copilot finding: the migration's own docstring used to tell an
    # installation on a non-default MySQL collation to "pass fold=False" -
    # advice that was never actually actionable, since the migration's own
    # RunPython callback is what supplies that argument, not the consumer.
    # KIOBLOG_SLUG_FOLD is the real, working escape hatch; this proves it
    # actually overrides the vendor guess rather than just being documented.
    #
    # Separate class, not a method added to DeduplicatePostSlugsMigrationTests
    # above: KIOBLOG_SLUG_FOLD must be set before the migration itself runs,
    # so this needs the migrate step inside the (overridden-settings) test
    # method, not in a shared setUp that runs before any per-test override.
    migrate_from = ("kioblog", "0006_post_content_markdownx")
    migrate_to = ("kioblog", "0007_enforce_unique_post_slugs")

    def tearDown(self) -> None:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    @override_settings(KIOBLOG_SLUG_FOLD=True)
    def test_setting_true_forces_folding_even_on_a_case_sensitive_backend(self) -> None:
        # This repo's real connection is SQLite - the migration's own vendor
        # check alone would resolve to False here, same as every other test
        # in this file. Forcing True via the setting must still fold "Foo"
        # and "foo" together, proving the override actually reaches
        # deduplicate_slugs and isn't shadowed by the vendor check.
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])

        old_apps = executor.loader.project_state([self.migrate_from]).apps
        User = old_apps.get_model("auth", "User")
        Category = old_apps.get_model("kioblog", "Category")
        Post = old_apps.get_model("kioblog", "Post")
        user = User.objects.create(username="foldsettingtestuser")
        category = Category.objects.create(title="cat", slug="fold-setting-cat")
        case_first = Post.objects.create(title="E", content="x", user=user, category=category, slug="Foo")
        case_second = Post.objects.create(title="F", content="x", user=user, category=category, slug="foo")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([self.migrate_to])

        new_apps = executor.loader.project_state([self.migrate_to]).apps
        Post = new_apps.get_model("kioblog", "Post")
        self.assertEqual(Post.objects.get(pk=case_first.pk).slug, "Foo")
        self.assertEqual(Post.objects.get(pk=case_second.pk).slug, "foo-2")


class PostUpdatedFieldStateTests(SimpleTestCase):
    def test_does_not_persist_its_one_off_backfill_default(self) -> None:
        # Without preserve_default=False, the timezone.now default used to
        # backfill existing rows gets baked into the ongoing migration state
        # even though Post.updated has none (only auto_now=True) - confirmed
        # with `makemigrations --check --dry-run`, which then proposes a
        # no-op AlterField purely to reconcile that phantom default away.
        module = importlib.import_module("kioblog.migrations.0008_post_updated")
        add_field = module.Migration.operations[0]
        self.assertFalse(add_field.preserve_default)


class PostUpdatedBackfillMigrationTests(TransactionTestCase):
    # TransactionTestCase, not TestCase, for the same reason as the classes
    # above: reversing a migration needs SQLite's foreign_keys pragma
    # toggled, which it refuses mid-transaction.
    migrate_from = ("kioblog", "0007_enforce_unique_post_slugs")
    migrate_to = ("kioblog", "0008_post_updated")

    def setUp(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])

        old_apps = executor.loader.project_state([self.migrate_from]).apps
        User = old_apps.get_model("auth", "User")
        Category = old_apps.get_model("kioblog", "Category")
        Post = old_apps.get_model("kioblog", "Post")

        user = User.objects.create(username="migrationtestuser")
        category = Category.objects.create(title="cat", slug="cat")
        # An old post, "published" long before this migration ever runs -
        # the field this migration is retrofitting doesn't exist yet at 0007.
        self.old_published = timezone.now() - timezone.timedelta(days=365)
        self.post = Post.objects.create(
            title="old post", content="x", user=user, category=category, slug="s", published=self.old_published
        )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([self.migrate_to])
        self.new_apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_backfills_updated_from_published_not_the_deploy_moment(self) -> None:
        # Left at the AddField's own default, every pre-existing post would
        # report "updated" at the moment this migration ran - exactly what
        # PostSitemap.lastmod (sitemap.py) exists to not do, and a likely
        # one-time mass recrawl trigger for a site upgrading kioblog.
        Post = self.new_apps.get_model("kioblog", "Post")
        post = Post.objects.get(pk=self.post.pk)
        self.assertEqual(post.updated, self.old_published)

    def test_a_real_save_after_the_migration_still_moves_it(self) -> None:
        # Confirms auto_now itself is intact after the backfill overwrites
        # its one-off default - this migration's RunPython uses .update(),
        # which bypasses save()/auto_now entirely, so it's worth confirming
        # the field still behaves normally once code starts touching it.
        Post = self.new_apps.get_model("kioblog", "Post")
        post = Post.objects.get(pk=self.post.pk)
        post.title = "edited"
        post.save()
        post.refresh_from_db()
        self.assertGreater(post.updated, self.old_published)


class DeduplicateCategorySlugsMigrationTests(TransactionTestCase):
    migrate_from = ("kioblog", "0008_post_updated")
    migrate_to = ("kioblog", "0009_enforce_unique_category_slugs")

    def setUp(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])

        old_apps = executor.loader.project_state([self.migrate_from]).apps
        Category = old_apps.get_model("kioblog", "Category")

        # Three categories already sharing a slug, plus an unrelated one that
        # must be left alone - all only possible because 0008 has no
        # constraint on Category.slug yet.
        self.first = Category.objects.create(title="A", slug="dup")
        self.second = Category.objects.create(title="B", slug="dup")
        self.third = Category.objects.create(title="C", slug="dup")
        self.unrelated = Category.objects.create(title="D", slug="fine")
        # "dup" colliding would naturally rename to "dup-2" - except that's
        # already someone else's real slug. Every model but Category was
        # already unique by the time this test was written, which is why
        # this scenario (and the one below) live here rather than as a
        # lighter unit test - after this migration there is no slugged model
        # left the ORM will let collide outside a reversed migration state.
        self.taken = Category.objects.create(title="Taken", slug="dup-2")

        max_length = Category._meta.get_field("slug").max_length
        long_slug = "x" * max_length
        self.long_first = Category.objects.create(title="Long A", slug=long_slug)
        self.long_second = Category.objects.create(title="Long B", slug=long_slug)
        # "Foo"/"foo": distinct Python strings, so the pre-0009 schema (no
        # constraint yet) accepts both - but a case-insensitive collation
        # (MySQL's default, for one) would treat them as the same value for
        # a unique index. Also moved here from the old test_slugs.py: with
        # Category constrained too, there's no model left the ORM will let
        # collide outside a reversed migration state like this one.
        self.case_first = Category.objects.create(title="Case A", slug="Foo")
        self.case_second = Category.objects.create(title="Case B", slug="foo")
        # Same reasoning, for an accent-insensitive collation instead of a
        # case-insensitive one (MySQL's `*_ai_ci` family).
        self.accent_first = Category.objects.create(title="Accent A", slug="café")
        self.accent_second = Category.objects.create(title="Accent B", slug="cafe")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([self.migrate_to])
        self.new_apps = executor.loader.project_state([self.migrate_to]).apps
        self.max_length = max_length

    def tearDown(self) -> None:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_collisions_are_renamed_keeping_the_first_by_id(self) -> None:
        Category = self.new_apps.get_model("kioblog", "Category")
        self.assertEqual(Category.objects.get(pk=self.first.pk).slug, "dup")
        self.assertEqual(Category.objects.get(pk=self.second.pk).slug, "dup-3")
        self.assertEqual(Category.objects.get(pk=self.third.pk).slug, "dup-4")

    def test_never_renames_onto_an_already_taken_slug(self) -> None:
        Category = self.new_apps.get_model("kioblog", "Category")
        self.assertEqual(Category.objects.get(pk=self.taken.pk).slug, "dup-2")

    def test_truncates_to_stay_within_max_length(self) -> None:
        Category = self.new_apps.get_model("kioblog", "Category")
        self.assertEqual(Category.objects.get(pk=self.long_first.pk).slug, "x" * self.max_length)
        renamed = Category.objects.get(pk=self.long_second.pk).slug
        self.assertEqual(renamed, f"{'x' * (self.max_length - 2)}-2")
        self.assertLessEqual(len(renamed), self.max_length)

    def test_unrelated_slug_is_untouched(self) -> None:
        Category = self.new_apps.get_model("kioblog", "Category")
        self.assertEqual(Category.objects.get(pk=self.unrelated.pk).slug, "fine")

    def test_case_variants_are_left_alone_on_a_case_sensitive_backend(self) -> None:
        # The migration's own vendor check, not a passed-in flag, is what
        # decides fold here - this test's real connection is SQLite, so it
        # should resolve to False and leave both alone. Mirrors 0007's own
        # test_case_variants_are_left_alone_on_a_case_sensitive_backend for
        # Post.
        Category = self.new_apps.get_model("kioblog", "Category")
        self.assertEqual(Category.objects.get(pk=self.case_first.pk).slug, "Foo")
        self.assertEqual(Category.objects.get(pk=self.case_second.pk).slug, "foo")

    def test_accent_variants_are_left_alone_on_a_case_sensitive_backend(self) -> None:
        Category = self.new_apps.get_model("kioblog", "Category")
        self.assertEqual(Category.objects.get(pk=self.accent_first.pk).slug, "café")
        self.assertEqual(Category.objects.get(pk=self.accent_second.pk).slug, "cafe")

    def test_every_row_survives_with_a_distinct_slug(self) -> None:
        Category = self.new_apps.get_model("kioblog", "Category")
        slugs = list(Category.objects.values_list("slug", flat=True))
        self.assertEqual(len(slugs), 11)
        self.assertEqual(len(slugs), len(set(slugs)))


class CategorySlugFoldSettingOverrideMigrationTests(TransactionTestCase):
    # Mirrors PostSlugFoldSettingOverrideMigrationTests above, for 0009.
    # Copilot finding, real: 0009 never read KIOBLOG_SLUG_FOLD at all before
    # this fix - an installation that set it to override 0007's vendor-only
    # guess for Post.slug had no way to do the same for Category.slug, even
    # though both migrations exist for exactly the same reason.
    migrate_from = ("kioblog", "0008_post_updated")
    migrate_to = ("kioblog", "0009_enforce_unique_category_slugs")

    def tearDown(self) -> None:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    @override_settings(KIOBLOG_SLUG_FOLD=True)
    def test_setting_true_forces_folding_even_on_a_case_sensitive_backend(self) -> None:
        # This repo's real connection is SQLite - the migration's own vendor
        # check alone would resolve to False here. Forcing True via the
        # setting must still fold "Foo" and "foo" together, proving the
        # override actually reaches deduplicate_slugs for Category too.
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])

        old_apps = executor.loader.project_state([self.migrate_from]).apps
        Category = old_apps.get_model("kioblog", "Category")
        case_first = Category.objects.create(title="Case A", slug="Foo")
        case_second = Category.objects.create(title="Case B", slug="foo")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([self.migrate_to])

        new_apps = executor.loader.project_state([self.migrate_to]).apps
        Category = new_apps.get_model("kioblog", "Category")
        self.assertEqual(Category.objects.get(pk=case_first.pk).slug, "Foo")
        self.assertEqual(Category.objects.get(pk=case_second.pk).slug, "foo-2")


class DeduplicateSlugsUsingParameterTests(SimpleTestCase):
    def test_using_is_threaded_to_the_manager_and_save(self) -> None:
        # A true cross-database check needs a second configured alias with
        # its own test database, which this repo's dev settings don't set up
        # - this instead proves the wiring itself: `using` reaches both the
        # query and the write, which is what actually fixes reading/writing
        # the "default" alias regardless of which connection is migrating.
        # No real model needed (nothing here touches the database), which is
        # also why this doesn't need Category as a fixture the way the
        # collision scenarios above do.
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

    def test_fold_true_treats_case_and_accent_variants_as_colliding(self) -> None:
        # Both real migration tests above run against this repo's own SQLite
        # connection, which always resolves the migrations' own
        # fold=(vendor == "mysql") to False - neither one ever actually
        # exercises fold=True causing a rename. This is that coverage,
        # ported from the old test_slugs.py (deleted once Category itself
        # became constrained, so it could no longer create real colliding
        # rows via the ORM to prove this against).
        foo = MagicMock(slug="Foo")
        foo2 = MagicMock(slug="foo")
        cafe_accented = MagicMock(slug="café")
        cafe_plain = MagicMock(slug="cafe")
        fake_model = MagicMock()
        rows = [foo, foo2, cafe_accented, cafe_plain]
        fake_model.objects.using.return_value = fake_model.objects
        fake_model.objects.only.return_value.order_by.return_value = rows
        fake_model._meta.get_field.return_value.max_length = 200

        deduplicate_slugs(fake_model, fold=True)

        foo2.save.assert_called_once_with(using=None, update_fields=["slug"])
        self.assertEqual(foo2.slug, "foo-2")
        cafe_plain.save.assert_called_once_with(using=None, update_fields=["slug"])
        self.assertEqual(cafe_plain.slug, "cafe-2")
        foo.save.assert_not_called()
        cafe_accented.save.assert_not_called()

    def test_fold_false_leaves_case_and_accent_variants_untouched(self) -> None:
        foo = MagicMock(slug="Foo")
        foo2 = MagicMock(slug="foo")
        cafe_accented = MagicMock(slug="café")
        cafe_plain = MagicMock(slug="cafe")
        fake_model = MagicMock()
        rows = [foo, foo2, cafe_accented, cafe_plain]
        fake_model.objects.using.return_value = fake_model.objects
        fake_model.objects.only.return_value.order_by.return_value = rows
        fake_model._meta.get_field.return_value.max_length = 200

        deduplicate_slugs(fake_model, fold=False)

        foo.save.assert_not_called()
        foo2.save.assert_not_called()
        cafe_accented.save.assert_not_called()
        cafe_plain.save.assert_not_called()

    def test_default_is_fold_false_the_safe_non_destructive_choice(self) -> None:
        # Copilot finding, real: the two tests above always pass fold=
        # explicitly, so neither actually proves what the *default* itself
        # does - a future change to that default (back to the original,
        # backwards fold=True) could silently reintroduce destructive
        # folding on every uncovered call site without failing either one.
        # This is that coverage, ported from the old test_slugs.py (deleted
        # once Category itself became constrained) rather than dropped along
        # with it.
        foo = MagicMock(slug="Foo")
        foo2 = MagicMock(slug="foo")
        cafe_accented = MagicMock(slug="café")
        cafe_plain = MagicMock(slug="cafe")
        fake_model = MagicMock()
        rows = [foo, foo2, cafe_accented, cafe_plain]
        fake_model.objects.using.return_value = fake_model.objects
        fake_model.objects.only.return_value.order_by.return_value = rows
        fake_model._meta.get_field.return_value.max_length = 200

        deduplicate_slugs(fake_model)

        foo.save.assert_not_called()
        foo2.save.assert_not_called()
        cafe_accented.save.assert_not_called()
        cafe_plain.save.assert_not_called()
