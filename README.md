# Media Library

> 🇬🇧 English | [🇷🇺 Русский](README.ru.md) | [🇫🇷 Français](README.fr.md) | [🇩🇪 Deutsch](README.de.md)

[![CI](https://github.com/DogNellaf/virtual-library/actions/workflows/ci.yml/badge.svg)](https://github.com/DogNellaf/virtual-library/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/DogNellaf/virtual-library)](https://github.com/DogNellaf/virtual-library/releases)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB)
![Django](https://img.shields.io/badge/django-6.1-092E20)
![PostgreSQL](https://img.shields.io/badge/postgresql-17-4169E1)
![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-orange)

A media library for a public library. Staff upload images, documents and other
files in the admin panel and sort them into categories. Visitors browse the
catalog, search it, preview images and download files. The interface is in
English, Russian, French and German and has a dark theme and a phone layout.

![Catalog](docs/screenshots/en/catalog.png)

## Quick start

```bash
docker compose up --build
```

Open <http://localhost:8000>. The stack starts PostgreSQL and the app and fills
the library with 28 generated files in 5 categories. To upload files, press
**Manage** and sign in as **demo / demo12345**. The demo storage quota is 25 MB
and one upload is limited to 10 MB.

## Case study

### Problem

The library had a working prototype. It showed files in a grid and let staff
upload them in the admin. Behind that it had problems that only show up with
real use.

- To draw the storage bar, every page load opened every file on disk.
- All files were rendered at once and filtered in the browser.
- The quota was only displayed. Nothing stopped an upload that did not fit.
- File sizes were divided by 8, the storage bar showed a fraction instead of a
  percentage and crashed without a quota, and the sidebar counters were empty.
- With `DEBUG=False` neither static nor uploaded files were served.
- Deleting a category silently deleted all of its files.

### Solution

Everything the catalog needs is computed once, when a file is uploaded, and
stored next to it.

| Stored on upload | Used for |
|---|---|
| Size in bytes | The storage bar is one `SUM` query, the quota check |
| Type (image, document, audio and so on) | The type filter and the icons |
| Width and height | The details panel |
| WebP thumbnail up to 640 px | The grid loads a small preview instead of the original photo |
| Folded title, description and file name | Search that ignores case and "ё", served by a trigram index |

The catalog page runs at most 7 SQL queries whether the library holds 10 files
or 10 000, and a test fails if that number grows with the number of files.

### Engineering highlights

- **The quota cannot be overrun.** An upload locks the single storage row,
  sums the stored sizes and only then saves the file. Two parallel uploads that
  each fit on their own but not together are serialized, and the second one is
  rejected. A test runs that race on PostgreSQL with two threads, and it fails
  as soon as the lock is removed.

  ```python
  def reserve_space(size: int, replacing: File | None = None) -> None:
      Storage.load()
      storage = Storage.objects.select_for_update().get(pk=1)
      if not storage.quota_bytes:
          return
      free = storage.quota_bytes - used_bytes(exclude=replacing)
      if size > free:
          raise QuotaExceeded(...)
  ```

  The admin wraps the whole add and change view in a transaction, so the form
  takes the lock in `clean()` and keeps it until the file is saved. A quota error
  is shown in the form next to the file field.
- **The catalog state is in the URL.** Search, category, file type, sorting,
  grid or list view, page and the selected file are query parameters. A link can
  be shared, the page survives a reload and the back button works. Invalid
  values are dropped one by one instead of failing the page.
- **It works without JavaScript.** Links and forms do everything, including the
  details panel, the language and theme menus and the full-size view (CSS
  `:target`). A 40-line script only adds Escape and `/` shortcuts and closes
  menus on an outside click.
- **Files are identified by content.** Pillow decides whether a file is an
  image, so a PDF renamed to `.png` is not shown as one. Thumbnails respect EXIF
  rotation, and oversized images (decompression bombs) are skipped.
- **Files on disk follow the database.** Replacing or deleting a file removes
  the old file and thumbnail only after the transaction commits, so a rollback
  never leaves a row that points to nothing.
- **Search ignores case and "ё" and uses an index.** Each file stores its
  title, description and file name in lower case with ё replaced by е, and the
  query is folded the same way, so `Ёлка` finds `ёлка` and `елка`. A trigram GIN
  index (`pg_trgm`) serves the substring search, and a test checks that the
  query plan uses it.
- **Existing data is migrated.** A data migration fills sizes, types and
  thumbnails for files uploaded before the overhaul and renames duplicate
  categories before the name becomes unique. A test runs it on prototype data.

### Security

- Uploaded files have no public URL. They are streamed by views. Downloads are
  `Content-Disposition: attachment` with the original name, and only raster
  images are ever shown inline, so an uploaded SVG or HTML file cannot run
  scripts on the site.
- A strict Content Security Policy (`script-src 'self'`, no inline scripts or
  styles, no third-party origins) on every page, including the admin. The smoke
  test fails on any CSP violation in the browser console.
- The app refuses to start in production without `DJANGO_SECRET_KEY`.
  `check --deploy` passes with no warnings (HSTS, HTTPS redirect, secure cookies,
  `X-Frame-Options: DENY`). The health check is exempt from the HTTPS redirect,
  so the container health check works behind a proxy.
- The image runs as a non-root user and installs wheels only.
- The superuser from `ADMIN_USERNAME` and `ADMIN_PASSWORD` is created once.
  A password changed in the admin is no longer reset on the next restart.
- The demo account can manage files and categories but not users.

### Localization

- English source strings with Russian, French and German gettext catalogs in
  `locale/`, including plural forms ("2 файла", "5 файлов", "2 fichiers",
  "2 Dateien") and model names in the admin.
- The language comes from a cookie set by the language menu, then from the
  browser. Dates and file sizes follow the language ("Oct. 3, 2026" and
  "3 октября 2026 г.", "35.2 KB" and "35,2 КБ").
- CI checks that the compiled `.mo` catalogs match the `.po` sources.

### Architecture

```mermaid
flowchart LR
    V[Visitor] -->|GET, query string state| C[Catalog views]
    S[Staff] -->|upload| A[Django admin]
    A -->|clean, lock storage row| Q[services.reserve_space]
    A --> M[File.save]
    M -->|Pillow| T[media.inspect<br/>type, size, thumbnail]
    M --> DB[(PostgreSQL)]
    M --> FS[/Media volume/]
    C -->|at most 7 queries| DB
    C -->|stream with safe headers| FS
```

| Module | Responsibility |
|---|---|
| `catalog/views.py` | Catalog page, file thumbnails, previews and downloads, theme, health check |
| `catalog/models.py` | Categories, files with stored metadata, the storage row |
| `catalog/services.py` | Quota check under a row lock, uploads, storage summary |
| `catalog/media.py` | Type detection by content, thumbnails, file cleanup |
| `catalog/admin.py` | Upload form with quota and size checks, thumbnails in lists |
| `catalog/demo.py`, `seed_demo` | Generated demo images, documents, audio and archives |
| `docker/smoke_test.py` | Browser walk through the catalog and the admin |

### What the overhaul changed

The project started as a prototype for one library. Turning it into a
maintained product involved

- storing file metadata and thumbnails instead of reading files on every
  request, with a data migration for existing rows;
- enforcing the quota under a row lock and protecting categories with files;
- moving search, filters, sorting and pagination to the server, with the whole
  state in the URL;
- serving files through views instead of a public folder, and adding a CSP;
- replacing the Tailwind and icon CDNs with hand-written CSS and an SVG sprite,
  and django-jet with the standard admin;
- adding the Russian, French and German translations, the dark theme and the
  phone layout;
- moving settings to environment variables and upgrading to Django 6.1,
  Python 3.13 and PostgreSQL 17;
- adding tests, Docker, CI with a browser smoke test, demo data and releases.

## Screenshots

| Details panel | Full-size view |
|---|---|
| ![Details](docs/screenshots/en/details.png) | ![Full-size view](docs/screenshots/en/zoom.png) |

| List view with a document | Dark theme |
|---|---|
| ![List](docs/screenshots/en/list.png) | ![Dark theme](docs/screenshots/en/dark.png) |

| Phone | Phone, details |
|---|---|
| ![Phone](docs/screenshots/en/mobile.png) | ![Phone details](docs/screenshots/en/mobile-details.png) |

| Admin file list | Admin sign-in with the demo account |
|---|---|
| ![Admin files](docs/screenshots/en/admin-files.png) | ![Admin sign-in](docs/screenshots/en/admin-login.png) |

## Running without Docker

You need Python 3.12 or newer and PostgreSQL. The database from the compose
file is published on `localhost` and matches the default `DATABASE_URL`.

```bash
docker compose up --detach db  # PostgreSQL on localhost:5432
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=True DEMO_USERNAME=demo DEMO_PASSWORD=demo12345
python manage.py migrate
python manage.py seed_demo     # optional demo content and account
python manage.py runserver
```

## Configuration

Settings come from environment variables or a `.env` file. See
[`.env.example`](.env.example) for a commented production example.

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Secret key, required when `DJANGO_DEBUG=False` | a fixed key in debug |
| `DJANGO_DEBUG` | Debug mode | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names | `localhost` in debug |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origins allowed to post forms | none |
| `DJANGO_TIME_ZONE` | Time zone for dates | `UTC` |
| `DATABASE_URL` | PostgreSQL database, for example `postgres://user:pass@host/db` | `postgres://library:library@localhost:5432/library` |
| `DATABASE_PORT` | Port of the compose database on `localhost` | `5432` |
| `MEDIA_ROOT` | Directory for uploaded files | `./media` |
| `STORAGE_QUOTA_BYTES` | Initial quota for all files, `0` for no limit, then editable in the admin | 50 GB |
| `FILE_UPLOAD_MAX_BYTES` | Limit for one upload | 512 MB |
| `CATALOG_PAGE_SIZE` | Files per catalog page | `24` |
| `HTTPS` | HTTPS redirect, HSTS and secure cookies | on unless debug |
| `USE_X_FORWARDED_PROTO` | Trust `X-Forwarded-Proto` from a TLS proxy | `False` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Superuser created on start if missing | none |
| `DEMO_SEED` | Fill an empty library with demo content on start (Docker) | `False`, `True` in compose |
| `DEMO_USERNAME`, `DEMO_PASSWORD` | Demo account, shown on the sign-in page | none |
| `LOG_LEVEL` | Log level | `INFO` |

`python manage.py seed_demo --reset` deletes all files and categories and
creates the demo content again.

## Tests

```bash
# the tests need PostgreSQL, the one from compose will do
docker compose up --detach db
ruff check . && ruff format --check .
coverage run manage.py test --settings=virtual_library.settings_test && coverage report

# browser smoke test and screenshots against a running stack
docker compose up --build --detach --wait
python -m playwright install chromium
python docker/smoke_test.py
python scripts/screenshots.py
```

There are 70 tests with 99% coverage, and the CI threshold is 90%. CI runs them
on PostgreSQL 17 with Python 3.12 and 3.13, including the parallel upload race
and the check that search uses the trigram index. It also checks migrations,
translations and the production settings, then builds the image, starts the
stack and runs the browser smoke test. It uploads and deletes a file through the
admin and fails on any console error.

## Project structure

```
├── catalog/
│   ├── management/commands/   # seed_demo, ensure_admin
│   ├── migrations/
│   ├── static/catalog/        # CSS, SVG icons, a small script
│   ├── templates/catalog/
│   ├── tests/
│   ├── admin.py  media.py  models.py  services.py  views.py
├── locale/                    # Russian, French and German translations
├── templates/                 # 404 page, admin sign-in
├── virtual_library/           # settings and URLs
├── docker/                    # entrypoint and browser smoke test
├── scripts/screenshots.py
├── docs/screenshots/
├── Dockerfile
├── docker-compose.yml
└── .github/                   # CI, releases, Dependabot
```

## License

[PolyForm Noncommercial 1.0.0](LICENSE). Use, modification and redistribution
are allowed for any noncommercial purpose, provided the notice
`Copyright (c) 2026 DogNellaf` is kept. Commercial use requires a separate
license, contact [DogNellaf](https://github.com/DogNellaf).
