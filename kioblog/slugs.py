"""Slug de-duplication shared by migrations that retrofit `unique=True` onto
a slug field that was never constrained at the database level.

An existing installation may already have duplicate slugs sitting in its
database - nothing before that migration stopped them from being created.
Adding the constraint outright would fail `migrate` for anyone in that
situation, so the migration renames the losers deterministically instead of
refusing to run.
"""


def deduplicate_slugs(model, slug_field="slug", order_by="pk"):
    """Rename every slug collision on `model` to `<slug>-2`, `<slug>-3`, ...

    The first row (by `order_by`) to use a given slug keeps it; later rows
    sharing it are renamed. `model` can be a real model class or the
    historical model a migration's RunPython receives from `apps.get_model` -
    only `.objects`, `getattr`/`setattr` and `.save()` are used, all of which
    historical models support.
    """
    max_length = model._meta.get_field(slug_field).max_length
    rows = list(model.objects.order_by(order_by))
    # Snapshot every slug that already exists, so a rename never lands on one
    # that belongs to a row this loop hasn't reached yet - that row keeps its
    # original slug (it isn't itself a duplicate), so the value stays taken.
    existing_slugs = {getattr(obj, slug_field) for obj in rows}
    seen = set()

    for obj in rows:
        slug = getattr(obj, slug_field)
        if slug not in seen:
            seen.add(slug)
            continue

        suffix = 2
        candidate = f"{slug[: max_length - len(f'-{suffix}')]}-{suffix}"
        while candidate in seen or candidate in existing_slugs:
            suffix += 1
            candidate = f"{slug[: max_length - len(f'-{suffix}')]}-{suffix}"

        seen.add(candidate)
        setattr(obj, slug_field, candidate)
        obj.save(update_fields=[slug_field])
