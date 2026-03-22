# kioblog — Agent & Copilot Instructions

## Project Overview

`kioblog` is a reusable Django application that provides a simple blog engine. It is distributed as a Python package on PyPI and meant to be installed into any Django project.

- **Package name:** `kioblog`
- **Current branch for active development:** `django5`
- **Default/stable branch:** `main`
- **Repository:** https://github.com/Eric-Bujeque/kioblog

## Project Structure

```
kioblog/          # The reusable Django app (the package that gets published)
kioblogdev/       # A local Django project used only for development/testing
manage.py         # Dev project management script
setup.py          # Package metadata and build configuration
setup.cfg         # long_description source
pyproject.toml    # Build system declaration (setuptools)
requirements.txt  # Dev dependencies
```

Key files inside `kioblog/`:
- `models.py` — `Post` and `SiteMeta` models
- `views.py` — Class-based views for listing and reading posts
- `urls.py` — URL patterns for the app
- `admin.py` — Django admin registrations
- `context_preprocessors.py` — Template context processors
- `decorators.py` — Custom decorators
- `sitemap.py` — Django sitemap integration
- `migrations/` — Database migrations
- `templates/kioblog/` — HTML templates (base, home, post, includes)
- `static/kioblog/css/` — Custom CSS
- `tests/` — Unit and view tests

## Tech Stack

- **Framework:** Django 5.1+
- **Database (dev):** SQLite (`db.sqlite3`)
- **Rich text editor:** django-summernote
- **Robots:** django-robots
- **Python:** 3.8+

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Running Tests

```bash
python manage.py test kioblog.tests
```

## Conventions

- Keep the `kioblog/` app self-contained and reusable — no hard dependencies on `kioblogdev/`.
- `kioblogdev/` is development-only and must never be included in the published package (already excluded in `setup.py`).
- `media/` is local dev only — never commit it.
- Migrations live inside the package (`kioblog/migrations/`) so they ship with the library.
- Templates and static files are declared in `setup.py` under `package_data` — update that list if new files are added.
- Version is set in `setup.py` (`version=`). Bump it before publishing a new release.

## Publishing

See [PUBLISH.md](PUBLISH.md) for the full release workflow.
