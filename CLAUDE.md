# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`kioblog` is a **reusable Django blog app** distributed as a PyPI package (`pip install kioblog`). The package itself is the `kioblog/` directory. `kioblogdev/` is a throwaway Django project that exists only to run the app during development, tests, and migrations — it is excluded from the published package (`find_packages(exclude=('kioblogdev', 'media'))` in [setup.py](setup.py)). Consumers mount the app under their own URL prefix (e.g. `/blog/`) and re-skin it by overriding templates.

## Commands

All commands run against the dev project via `manage.py` (which points at `kioblogdev.settings`):

```bash
python manage.py test -v 2              # run the full test suite (this is what CI runs)
python manage.py test kioblog.tests.test_views.KioblogViews.test_post   # single test
python manage.py makemigrations kioblog # after changing models.py
python manage.py migrate
python manage.py runserver              # dev server; blog lives at /blog/, admin at /admin/
flake8                                  # lint (config in .flake8; CI fails on lint errors)
```

CI ([.circleci/config.yml](.circleci/config.yml)) runs `flake8` then `python3 manage.py test -v 2` on Python 3.8. `.flake8` ignores `D203` and `E501` (line length), and excludes `manage.py`.

## Architecture

The app is deliberately small; the pieces that matter span several files:

- **Content is Markdown, rendered through a custom pipeline.** `Post.content` holds **Markdown**; `Post.content_html` (property) renders it via [kioblog/markdown/render.py](kioblog/markdown/render.py) and templates use `{{ post.content_html|safe }}`. The pipeline (`render_markdown`) wires a custom `CodeChromeExtension` plus Python-Markdown's `toc`. `Post.toc` exposes the generated table of contents (from `<h2>` headings) for the "On this page" index; `Post.reading_time` estimates minutes at ~200 wpm. Rendering is cached per instance in `Post._render()`. `Post.first_paragraph()` still exists (regex over HTML) but cards use `Post.excerpt`.

- **The code-block DOM is a contract, not a detail.** [kioblog/markdown/code_chrome.py](kioblog/markdown/code_chrome.py) is a Markdown preprocessor that parses the fence info-string `lang:filename`, highlights with Pygments, and emits the exact `<figure class="code-block">…` structure and class names from **section 5 of SPEC_ericbujeque_blog.md**. kioblog *emits* this markup; the consumer only styles it. **Do not rename these classes or change the structure** — `kioblog/tests/test_markdown.py` asserts them. Token colors live in [kioblog/markdown/pygments_onedark.py](kioblog/markdown/pygments_onedark.py) (`OneDarkStyle`); the shipped stylesheet `kioblog/static/kioblog/code.css` is **generated** from it via `python manage.py regenerate_code_css` — edit the style, never the CSS by hand.

- **`HomeView` serves three routes; `TagView`/`SearchView` are separate.** In [views.py](kioblog/views.py), `HomeView` (a `TemplateView`, not `ListView`) backs the index (`''`), pagination (`page/<int:page>`), and category (`category/<str:category>`) URLs. It filters `draft=False`, paginates at **5 per page**, and always returns `posts`, `page_range`, `recent_posts` (plus `category`, `featured_post`). **The first three keys are asserted by [test_views.py](kioblog/tests/test_views.py) — do not remove them.** `TagView` reuses `home.html`; `SearchView` (`search/?q=`) does an `icontains` over title/excerpt/content and renders `search.html`.

- **Recent-posts injection is split.** `HomeView`/`TagView`/`SearchView` set `recent_posts` directly. `PostView` (a `DetailView`) instead gets it from the `load_recent_posts` decorator in [decorators.py](kioblog/decorators.py), applied via `@method_decorator(..., name='dispatch')`. That decorator wraps the response, mutates `response.context_data`, then calls `.render()` — so it only works on unrendered `TemplateResponse`s. `PostView.get_context_data` adds `prev_post`/`next_post`/`related_posts`.

- **Site-wide context** comes from two context processors in [context_preprocessors.py](kioblog/context_preprocessors.py): `kioblog_settings` (flattens the `Meta` key/value model into a dict) and `kioblog_categories` (annotates each category with `post_count` of non-draft posts). Both must be registered in the consumer's `settings.py > TEMPLATES > context_processors` or the sidebar/settings render empty.

- **SEO** is `django-robots` (`robots.txt`) plus four `Sitemap` classes in [sitemap.py](kioblog/sitemap.py) (posts, categories, tags, main page), wired into a `sitemaps` dict in [urls.py](kioblog/urls.py). Note `<slug:slug>/` is the **last** URL pattern — new top-level routes (like `search/`) must be added before it or the slug matcher will swallow them.

- **Models** ([models.py](kioblog/models.py)): `Category` (with `post_count()`), `Tag`, `Post` (ordered `-published, -id`; M2M `tags`, `excerpt`, `is_featured`, `published`; `get_previous`/`get_next`/`related_posts` helpers), `Comment` (self-referential `parent` for threading), and `Meta` (arbitrary key/value settings surfaced via the context processor). `models.py` imports `render_markdown` at module load, so the `kioblog.markdown` package must import cleanly for migrations to run.

- **The admin editor is django-markdownx.** `PostAdmin` in [admin.py](kioblog/admin.py) subclasses `MarkdownxModelAdmin`, which only swaps in the markdown widget for `MarkdownxField` (not plain `TextField`) — that's why `Post.content` is declared as `MarkdownxField`, not `TextField`. The dev project sets `MARKDOWNX_MARKDOWNIFY_FUNCTION = 'kioblog.markdown.render.render_markdown'` so the admin live-preview matches the public render (same code chrome + toc). Consumers need `markdownx` in `INSTALLED_APPS` and its URLs included. **Gotcha:** `markdownx.urls` is mounted inside `kioblog/urls.py` (under the blog's own prefix, since kioblog doesn't know where it'll be mounted), but the client-side JS always POSTs to the site-absolute `MARKDOWNX_URLS_PATH` (default `/markdownx/markdownify/`) and `MARKDOWNX_UPLOAD_URLS_PATH` (default `/markdownx/upload/`, used when dragging an image into the editor). Any consumer must set both to `<their-prefix>/markdownx/markdownify/` and `<their-prefix>/markdownx/upload/` or the live preview / image upload 404s silently in the browser console.

- **Migration note:** `published` was added with `default=timezone.now`, then a data migration ([0005_backfill_published.py](kioblog/migrations/0005_backfill_published.py)) backfills it from the legacy `created` date so existing rows keep their real order. A stale `Page` model (created in `0001`, long removed from `models.py`) still lingers in migration state — `makemigrations` will offer to delete it; that deletion is **intentionally not bundled** into the feature migrations.

## Templates & static (the re-skin contract)

Templates live in `kioblog/templates/kioblog/` and static in `kioblog/static/kioblog/`. Consumers override templates by shadowing these paths. Because this is a distributed package, [MANIFEST.in](MANIFEST.in) `recursive-include`s templates and static — **any new template/static asset must ship via MANIFEST.in or it will be missing from the installed package** (this has caused release bugs before, see git history).

## Releasing

Version is hardcoded in **three places that must stay in sync**: `version` and `download_url` (the git tag) in [setup.py](setup.py), and the git tag itself. Bump, tag, and publish to PyPI. `requirements.txt` pins the dev project's deps; `install_requires` in setup.py declares the looser runtime floors (`Django>=3.0`, `Markdown`, `Pygments`, `django-markdownx`). When adding a static asset used by the render pipeline (e.g. a regenerated `code.css`), confirm it is committed — it ships via MANIFEST.in.

## Note on SPEC_ericbujeque_blog.md

`SPEC_ericbujeque_blog.md` is an untracked, disposable planning doc that drove the Markdown+Pygments pipeline, tags, search, and reading-time work (implemented in v0.2.0). Section 5 (the code-block DOM contract) is still the authoritative reference for the emitted markup and token colors. Treat the rest as historical roadmap — the code, not the spec, is now the source of truth.
