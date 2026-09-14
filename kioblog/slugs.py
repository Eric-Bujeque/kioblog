"""Slug de-duplication shared by migrations that retrofit `unique=True` onto
a slug field that was never constrained at the database level.

An existing installation may already have duplicate slugs sitting in its
database - nothing before that migration stopped them from being created.
Adding the constraint outright would fail `migrate` for anyone in that
situation, so the migration renames the losers deterministically instead of
refusing to run.

Migrations 0007 and 0009 both import `deduplicate_slugs` directly rather
than each keeping a frozen copy of it - a deliberate call, not an oversight.
Django's own "don't import live code into a migration" guidance is about
*models*: importing the real model class instead of `apps.get_model()`'s
historical one breaks replay against an old schema, which is exactly what
`apps.get_model()` exists to prevent. A plain algorithmic helper that only
touches the field name and value it's told about doesn't have that failure
mode. The real, narrower risk - this function's behaviour changing under a
migration that already shipped - is the reason to be conservative editing
it later: a change here should stay behaviourally compatible with every
migration that already depends on it (0007, 0009, and any added since),
not just pass today's tests.
"""


def deduplicate_slugs(model, slug_field="slug", order_by="pk", using=None):
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
    """
    manager = model.objects.using(using) if using else model.objects
    max_length = model._meta.get_field(slug_field).max_length
    rows = list(manager.order_by(order_by))
    # Snapshot every slug that already exists, so a rename never lands on one
    # that belongs to a row this loop hasn't reached yet - that row keeps its
    # original slug (it isn't itself a duplicate), so the value stays taken.
    #
    # Compared case-insensitively (.casefold(), not just the exact string):
    # a unique index under a case-insensitive collation - MySQL's default,
    # for instance - treats "Foo" and "foo" as the same value even though
    # they're different Python strings. Matching that pessimistically, rather
    # than trying to introspect each backend's actual collation, means a pair
    # that's only a real collision on some databases gets renamed everywhere.
    # Harmless where it wasn't strictly required: the loser just becomes
    # `-2`, `-3`, ... instead of being left alone.
    existing_keys = {getattr(obj, slug_field).casefold() for obj in rows}
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
        key = slug.casefold()
        if key not in seen:
            seen.add(key)
            continue

        suffix = next_suffix.get(key, 2)
        candidate = f"{slug[: max_length - len(f'-{suffix}')]}-{suffix}"
        while candidate.casefold() in seen or candidate.casefold() in existing_keys:
            suffix += 1
            candidate = f"{slug[: max_length - len(f'-{suffix}')]}-{suffix}"
        next_suffix[key] = suffix + 1

        seen.add(candidate.casefold())
        setattr(obj, slug_field, candidate)
        obj.save(using=using, update_fields=[slug_field])
