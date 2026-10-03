# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-10-03

The first release after the overhaul of the 2025 prototype.

### Added

- Thumbnails, image dimensions, file type and size stored on upload.
- Storage quota checked under a row lock, editable in the admin.
- Search by title, description and file name that ignores case and "ё".
- Filters by category and file type, sorting, grid and list views and pagination, all kept in the URL.
- Details panel with a full-size image view, also kept in the URL.
- Russian, French and German translations, dark theme and a phone layout.
- Health check, Content Security Policy and HTTPS settings for production.
- Demo content and a demo account for `docker compose up`.
- Tests on SQLite and PostgreSQL, a browser smoke test, CI, Dependabot and releases.

### Changed

- Django 5.2 to 6.1, Python 3.11 to 3.13, PostgreSQL 15 to 17.
- Files are served through the app with safe headers instead of the public `/media/` folder.
- django-jet replaced by the standard admin. Tailwind and icon CDNs replaced by local CSS and SVG.
- The admin password from the environment no longer overwrites one changed in the admin.
- A category that still has files cannot be deleted.

### Fixed

- File sizes were divided by 8 and the storage bar showed a fraction instead of a percentage.
- The storage bar crashed the page when no quota was set.
- File counts in the sidebar were always empty.
- Static and uploaded files were not served with `DEBUG=False`.

[1.0.0]: https://github.com/DogNellaf/virtual-library/releases/tag/v1.0.0
