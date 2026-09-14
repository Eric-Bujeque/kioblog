"""Proves migration 0007 is safe to run against a database that already has
duplicate Post slugs - the exact situation an existing installation upgrading
past this migration is in, and the one a plain `AlterField(unique=True)`
would fail on.

Builds real duplicate rows against the pre-0007 schema (which has no
constraint to stop them), then migrates forward and asserts every row
survives with a unique slug. This exercises the actual migration, not a
reimplementation of it - kioblog.slugs.deduplicate_slugs already has a
narrower unit-style check in test_slugs.py.
"""

import importlib

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase, override_settings


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
        # This is the actual, real-connection version of what test_slugs.py's
        # test_fold_false_leaves_case_and_accent_variants_untouched proves at
        # the unit level: the migration's own vendor check, not a passed-in
        # flag, is what decides fold here - this test's real connection is
        # SQLite, so it should resolve to False and leave both alone.
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


class PostUpdatedFieldMigrationTests(SimpleTestCase):
    def test_does_not_persist_its_one_off_backfill_default(self) -> None:
        # Without preserve_default=False, the timezone.now default used to
        # backfill existing rows gets baked into the ongoing migration state
        # even though Post.updated has none (only auto_now=True) - confirmed
        # with `makemigrations --check --dry-run`, which then proposes a
        # no-op AlterField purely to reconcile that phantom default away.
        module = importlib.import_module("kioblog.migrations.0008_post_updated")
        add_field = module.Migration.operations[0]
        self.assertFalse(add_field.preserve_default)
