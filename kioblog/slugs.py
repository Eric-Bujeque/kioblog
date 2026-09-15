"""Slug de-duplication shared by migrations that retrofit `unique=True` onto
a slug field that was never constrained at the database level.

An existing installation may already have duplicate slugs sitting in its
database - nothing before that migration stopped them from being created.
Adding the constraint outright would fail `migrate` for anyone in that
situation, so the migration renames the losers deterministically instead of
refusing to run.

Migrations that retrofit uniqueness onto some slug field import
`deduplicate_slugs` directly rather than each keeping a frozen copy of it -
a deliberate call, not an oversight. Django's own "don't import live code
into a migration" guidance is about *models*: importing the real model
class instead of `apps.get_model()`'s historical one breaks replay against
an old schema, which is exactly what `apps.get_model()` exists to prevent.
A plain algorithmic helper that only touches the field name and value it's
told about doesn't have that failure mode. The real, narrower risk - this
function's behaviour changing under a migration that already shipped - is
the reason to be conservative editing it later: a change here should stay
behaviourally compatible with every migration that already depends on it,
not just pass today's tests.
"""

import unicodedata


def _fold(slug):
    """Normalize a slug for comparison, matching a *permissive* real-world
    collation rather than an exact byte comparison.

    casefold() alone models case-insensitivity (MySQL's default collations
    treat "Foo" and "foo" as equal). NFKD-decomposing and dropping combining
    marks additionally models common accent-insensitive collations
    (MySQL's `*_ai_ci` family treats "café" and "cafe" as equal too) - this
    is a heuristic covering ordinary Latin-script accents, not a faithful
    reimplementation of any specific collation's exact rules. Confirmed
    directly (not just asserted) which locale-specific cases that leaves
    out: å/ä/ö and ß are NOT among them - NFKD decomposes å/ä/ö into a plain
    a/a/o plus a combining mark this function already drops, and casefold()
    already maps ß to "ss", so all four fold like any other accented
    character here. What's genuinely NOT attempted is Turkish dotless-i
    casing (casefold() is locale-independent, so "I" always folds towards
    ASCII "i", never Turkish's dotless "ı") and any other locale-specific
    *casing* rule - as opposed to the accent-stripping above, which is
    locale-independent by construction. Deliberately still pessimistic like
    the plain case-folding it extends: a pair only a real collision under
    some backend's collation gets renamed everywhere, which is harmless
    where it wasn't strictly required.
    """
    return "".join(c for c in unicodedata.normalize("NFKD", slug.casefold()) if not unicodedata.combining(c))


def deduplicate_slugs(model, slug_field="slug", order_by="pk", using=None, fold=False):
    """Rename every slug collision on `model` to `<slug>-2`, `<slug>-3`, ...

    The first row (by `order_by`) to use a given slug keeps it; later rows
    sharing it are renamed. `model` can be a real model class or the
    historical model a migration's RunPython receives from `apps.get_model` -
    only `.objects`, `getattr`/`setattr` and `.save()` are used, all of which
    historical models support.

    `using`: the database alias to read and write. A migration's default
    manager otherwise always hits the "default" alias regardless of which
    connection is actually being migrated - Django's own docs warn about
    this for RunPython. Pass `schema_editor.connection.alias`.

    `fold`: whether to compare slugs via `_fold()` (case/accent-insensitive)
    instead of exact strings. Defaults to False - the non-destructive
    choice - not True: slugs are public, user-facing identifiers (Post.slug
    is in every post URL), and on a case-sensitive backend (SQLite,
    PostgreSQL's defaults), two rows like "Foo" and "foo" are genuinely
    distinct values a real unique index would accept *both* of unchanged.
    Folding by default would silently rename a live, working, indexed URL
    on every backend that never needed it - the exact failure this
    migration exists to avoid causing - just to save a caller one explicit
    argument on the one backend family that does. A migration wrapper that
    actually needs folding (MySQL's permissive defaults) opts in
    explicitly, e.g. `fold=schema_editor.connection.vendor == "mysql"` (see
    migrations 0007 and 0009); this default only matters to a future caller
    who forgets to choose, and the safe choice for that caller is to do
    nothing rather than possibly break a live URL.

    A vendor check like that is itself only a heuristic for the collation
    MySQL ships with out of the box (`utf8mb4_0900_ai_ci` as of MySQL 8,
    and its `*_ai_ci`/`*_ci` predecessors) - it does not inspect the slug
    column's *actual* collation. An installation that deliberately
    configured a case/accent-sensitive one instead (`utf8mb4_bin`,
    `*_as_cs`) would still get folded by such a wrapper, even though its
    own unique index would have accepted both variants unchanged - the same
    unnecessary-rename failure this default exists to avoid on
    SQLite/PostgreSQL. Determining this from the column's real collation
    (`information_schema.columns`, or equivalent) instead of a vendor guess
    would close that gap, at the cost of backend-specific introspection
    this migration doesn't otherwise need - not done here as a deliberate
    scope call for what is a one-time, best-effort retrofit onto existing
    data, not a runtime guarantee. Migrations 0007 and 0009 both expose a
    settings override (`KIOBLOG_SLUG_FOLD`) for exactly this case, since
    "pass fold=False yourself" was never actually something an installation
    could do - the migration's own RunPython callback is what supplies this
    argument, not the consumer.
    """
    manager = model.objects.using(using) if using else model.objects
    max_length = model._meta.get_field(slug_field).max_length
    # .only(), not a bare .order_by(): this never reads or writes anything
    # but the pk and slug_field, but a plain queryset still fetches every
    # column of every row - Post.content is Markdown text, so on a database
    # with many or large posts that's real, unnecessary memory pressure
    # during `migrate` for fields this function never looks at. The pk is
    # always loaded regardless of .only()'s arguments, so it doesn't need
    # to be named here even when order_by is the default "pk"; stripped of
    # a leading "-" in case a caller ever orders by something else descending.
    rows = list(manager.only(slug_field, order_by.lstrip("-")).order_by(order_by))
    key_fn = _fold if fold else (lambda s: s)
    # Snapshot every slug that already exists, so a rename never lands on one
    # that belongs to a row this loop hasn't reached yet - that row keeps its
    # original slug (it isn't itself a duplicate), so the value stays taken.
    existing_keys = {key_fn(getattr(obj, slug_field)) for obj in rows}
    seen = set()
    # Remembers where the search left off for each base slug, so the next
    # duplicate of the *same* one doesn't re-scan candidates already claimed
    # by an earlier duplicate in this same collision group. Without it, a
    # group of k identical slugs costs Θ(k²) candidate checks (each one
    # restarting from -2 and re-walking every prior candidate) instead of
    # Θ(k) - negligible for a handful of duplicates, not for a large legacy
    # collision group on a slow upgrade path. Confirmed this doesn't change
    # any observable output by tracing it against every existing test
    # scenario by hand before relying on the tests alone to prove it.
    next_suffix = {}

    for obj in rows:
        slug = getattr(obj, slug_field)
        key = key_fn(slug)
        if key not in seen:
            seen.add(key)
            continue

        suffix = next_suffix.get(key, 2)
        candidate = f"{slug[: max_length - len(f'-{suffix}')]}-{suffix}"
        while key_fn(candidate) in seen or key_fn(candidate) in existing_keys:
            suffix += 1
            candidate = f"{slug[: max_length - len(f'-{suffix}')]}-{suffix}"
        next_suffix[key] = suffix + 1

        seen.add(key_fn(candidate))
        setattr(obj, slug_field, candidate)
        obj.save(using=using, update_fields=[slug_field])
