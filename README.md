# Kioblog

Kioblog is a small, reusable Django app that provides a simple blog (models, views,
admin integration and templates). It ships with default templates you can override
in your project.

**Quick Start**

- **Install:**

    ```bash
    pip install kioblog
    ```

- **Add to `INSTALLED_APPS`:**

    ```python
    INSTALLED_APPS = [
            # Django contrib apps required by Kioblog
            'django.contrib.sites',
            'django.contrib.sitemaps',

            # third-party (if you use admin wysiwyg)
            'django_summernote',

            # reusable app
            'kioblog',
    ]
    ```

- **Project URLs:** include the app's URLs (example mounts at `/blog/`):

    ```python
    from django.urls import path, include

    urlpatterns = [
            path('blog/', include('kioblog.urls')),
    ]
    ```

- **Media & upload settings (example):**

    ```python
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

    # Kioblog expects an `UPLOAD_TO` setting used by `Post.image`
    UPLOAD_TO = 'kioblog'
    ```

- **Migrate & run:**

    ```bash
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver
    ```

Visit `http://localhost:8000/blog/` (or wherever you mounted it) and the admin at
`/admin/` to add posts, categories and metadata.

**Features**

- `Post`, `Category`, `Comment` models and a small `Meta` (key/value) model.
- List and detail views with pagination and a simple sitemap implementation.
- Admin integration with `django-summernote` support for post content.
- Template hooks and context processors for site metadata and categories.

**Template overriding**

Place templates under your project templates directory using the same app namespace to
override defaults. Example files shipped with the app:

- `templates/kioblog/home.html`
- `templates/kioblog/post.html`

To override, create `templates/kioblog/post.html` in your project and Django will
use your version instead of the packaged one.

**Settings & integration notes**

- The app references a few site-level settings you should configure in your project:
    - `UPLOAD_TO` — used for `Post.image` upload location (string path).
    - `SITE_ID` — required if you enable `django.contrib.sites`.

- Optional third-party integrations used by the app:
    - `django-robots` (robots.txt)
    - `django-summernote` (admin WYSIWYG)

**Packaging & compatibility**

- Declared compatibility: Django 5+. Python 3.8–3.12 supported in metadata.
- If you install from source, prefer installing with `pip install .` from the project
    root which will respect `pyproject.toml` and `MANIFEST.in`.

**Recommendations & possible improvements**

- Rename the `Meta` model to avoid confusion with Django's inner `Meta` class (for
    example `SiteMeta` or `Setting`).
- Prefer `DateTimeField(auto_now_add=True)` for `created` timestamps on `Post` and
    `Comment` to preserve full time information.
- Add `unique=True` to `slug` fields (or enforce uniqueness per category for `Post`).
- Filter out `blocked` posts in site views and sitemaps (if that flag is used to hide
    content).
- Improve the packaging configuration in `setup.py`/`pyproject.toml` to use
    `setuptools.setup()` with correct `package_data` patterns or use `include_package_data`
    with a comprehensive `MANIFEST.in`.

**Tests**

Some simple tests are provided under `kioblog/tests/`. Running the project's test
suite will validate basic view behavior with Django's test client.

**Contributing & development**

If you plan to develop locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python manage.py migrate
python manage.py runserver
```

**License**

MIT
