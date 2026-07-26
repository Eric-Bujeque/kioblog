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
pre-commit run --all-files              # lint/format everything (same hooks CI runs)
pre-commit install                      # once per clone, to run the hooks on commit
```

**Lint/format is ruff, driven by pre-commit** ([.pre-commit-config.yaml](.pre-commit-config.yaml)); rules live in [ruff.toml](ruff.toml) (line-length 120, `E501` ignored, `kioblog/migrations` excluded). The rule set is pinned explicitly rather than relying on ruff's defaults, which shift between releases. `kioblog/static/kioblog/code.css` is excluded from the hooks because it is generated — a whitespace hook rewriting it would fight `regenerate_code_css`.

CI is GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)), on every push and PR, with three jobs: **lint** (runs the pre-commit hooks), **test** (`manage.py test -v 2`), and **package** (builds the sdist/wheel, `twine check`, and asserts templates/static/migrations are actually inside the wheel — MANIFEST.in omissions have shipped broken releases before). Everything runs on **Python 3.10**: `requirements.txt` pins Django 3.2, which supports no higher. Raising the Python version means bumping Django first.

Note CI deliberately does **not** run `makemigrations --check` — the stale `Page` model (see the migration note below) would fail it.

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

**The git tag is the version.** There is no `version=` in [setup.py](setup.py): `setuptools_scm` (wired up in [pyproject.toml](pyproject.toml)) derives it from the latest tag at build time. Nothing to keep in sync, and no PR needed just to bump a number.

The catch is that **a build must be able to see the tags**. `setuptools_scm` does not fail on a shallow checkout — it warns and emits a `0.1.devN+g<sha>` placeholder — so every job that runs `python -m build` checks out with `fetch-depth: 0`. `publish.yml` asserts the built filename matches the tag, which is what turns that silent failure into a loud one.

A release is three deliberate steps, and **both workflow steps are manual triggers in the Actions tab, not something that happens on merge**:

1. Merge whatever you want to ship to `main`.
2. Run **Tag release** ([tag-release.yml](.github/workflows/tag-release.yml)) and pick `patch`, `minor` or `major`. It reads the highest existing `vX.Y.Z` tag and does the arithmetic, so no version is ever typed. It refuses to run off any branch but `main`, refuses if `HEAD` is already a release tag (which would put two version numbers on one commit), and refuses if the computed tag somehow exists. Older non-canonical tags like `v0.1-alpha` are ignored by the maths.
3. Run **Publish to PyPI** ([publish.yml](.github/workflows/publish.yml)) and give it the tag step 2 printed.

Publishing never happens on its own. There is no `push: tags` trigger, deliberately: a tag pushed by step 3 wouldn't fire it anyway (GitHub does not start workflow runs for pushes made with `GITHUB_TOKEN`), so a tag pushed from a terminal behaving differently from one made by the workflow would be a trap. One manual trigger keeps the rule simple.

The publish run is `check-tag` → `validate` → `build` → `publish` → `release`. It re-runs the **whole** CI suite against the tagged commit (that's what `validate.yml`'s `ref` input is for — otherwise it would validate whatever branch the run was started from), verifies the tag matches the version actually built, uploads via **PyPI Trusted Publishing (OIDC)** with no stored API token, and finally opens a **GitHub release** with auto-generated notes and the sdist/wheel attached. The upload sits in the `pypi` GitHub environment, so adding required reviewers there gates it behind a manual approval.

Permissions are split per job on purpose: the OIDC upload holds only `id-token: write`, and only the release job gets `contents: write`.

`requirements.txt` pins the dev project's deps; `install_requires` in setup.py declares the looser runtime floors (`Django>=3.0`, `Markdown`, `Pygments`, `django-markdownx`). When adding a static asset used by the render pipeline (e.g. a regenerated `code.css`), confirm it is committed — it ships via MANIFEST.in, and the CI `package` job checks that.

## Note on SPEC_ericbujeque_blog.md

`SPEC_ericbujeque_blog.md` is an untracked, disposable planning doc that drove the Markdown+Pygments pipeline, tags, search, and reading-time work (implemented in v0.2.0). Section 5 (the code-block DOM contract) is still the authoritative reference for the emitted markup and token colors. Treat the rest as historical roadmap — the code, not the spec, is now the source of truth.
