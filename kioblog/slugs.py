"""Slug de-duplication shared by migrations that retrofit `unique=True` onto
a slug field that was never constrained at the database level.

An existing installation may already have duplicate slugs sitting in its
database - nothing before that migration stopped them from being created.
Adding the constraint outright would fail `migrate` for anyone in that
situation, so the migration renames the losers deterministically instead of
refusing to run.
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

    for obj in rows:
        slug = getattr(obj, slug_field)
        key = slug.casefold()
        if key not in seen:
            seen.add(key)
            continue

        suffix = 2
        candidate = f"{slug[: max_length - len(f'-{suffix}')]}-{suffix}"
        while candidate.casefold() in seen or candidate.casefold() in existing_keys:
            suffix += 1
            candidate = f"{slug[: max_length - len(f'-{suffix}')]}-{suffix}"

        seen.add(candidate.casefold())
        setattr(obj, slug_field, candidate)
        obj.save(using=using, update_fields=[slug_field])
