# Mediathek

> [🇬🇧 English](README.md) | [🇷🇺 Русский](README.ru.md) | [🇫🇷 Français](README.fr.md) | 🇩🇪 Deutsch

[![CI](https://github.com/DogNellaf/virtual-library/actions/workflows/ci.yml/badge.svg)](https://github.com/DogNellaf/virtual-library/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/DogNellaf/virtual-library)](https://github.com/DogNellaf/virtual-library/releases)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB)
![Django](https://img.shields.io/badge/django-6.1-092E20)
![PostgreSQL](https://img.shields.io/badge/postgresql-17-4169E1)
![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-orange)

Eine Mediathek für eine öffentliche Bibliothek. Mitarbeitende laden Bilder,
Dokumente und andere Dateien in der Verwaltung hoch und ordnen sie Kategorien
zu. Besucher durchstöbern den Katalog, durchsuchen ihn, sehen sich Bilder an und
laden Dateien herunter. Die Oberfläche gibt es auf Englisch, Russisch,
Französisch und Deutsch, mit dunklem Design und Layout für das Smartphone.

![Katalog](docs/screenshots/de/catalog.png)

## Schnellstart

```bash
docker compose up --build
```

Öffnen Sie <http://localhost:8000>. Der Stack startet PostgreSQL und die App und
füllt die Mediathek mit 28 generierten Dateien in 5 Kategorien. Zum Hochladen
klicken Sie auf **Verwalten** und melden sich mit **demo / demo12345** an. In der
Demo beträgt das Speicherkontingent 25 MB, eine Datei darf höchstens 10 MB groß
sein.

## Fallstudie

### Ausgangslage

Die Bibliothek hatte einen funktionierenden Prototyp. Er zeigte Dateien als
Raster und ließ Mitarbeitende sie in der Verwaltung hochladen. Dahinter steckten
Probleme, die erst im echten Betrieb auffallen.

- Für die Speicheranzeige öffnete jeder Seitenaufruf jede Datei auf der Platte.
- Alle Dateien wurden auf einmal ausgegeben und im Browser gefiltert.
- Das Kontingent wurde nur angezeigt. Nichts hielt einen Upload auf, der nicht
  mehr passte.
- Dateigrößen wurden durch 8 geteilt, die Speicheranzeige zeigte einen Bruchteil
  statt Prozent und stürzte ohne Kontingent ab, und die Zähler in der
  Seitenleiste blieben leer.
- Mit `DEBUG=False` wurden weder statische noch hochgeladene Dateien
  ausgeliefert.
- Das Löschen einer Kategorie löschte stillschweigend alle ihre Dateien.

### Lösung

Alles, was der Katalog braucht, wird einmal beim Hochladen berechnet und mit der
Datei gespeichert.

| Beim Hochladen gespeichert | Wofür |
|---|---|
| Größe in Bytes | Die Speicheranzeige ist eine `SUM`-Abfrage, die Kontingentprüfung |
| Typ (Bild, Dokument, Audio und so weiter) | Der Typfilter und die Symbole |
| Breite und Höhe | Das Detailfenster |
| WebP-Vorschaubild bis 640 px | Das Raster lädt eine kleine Vorschau statt des Originalfotos |
| Titel, Beschreibung und Dateiname in Kleinbuchstaben | Suche ohne Groß- und Kleinschreibung und „ё“, über einen Trigramm-Index |

Die Katalogseite stellt höchstens 7 SQL-Abfragen, egal ob die Mediathek 10 oder
10 000 Dateien enthält, und ein Test schlägt fehl, sobald die Zahl mit der Menge
der Dateien wächst.

### Technische Entscheidungen

- **Das Kontingent lässt sich nicht überschreiten.** Ein Upload sperrt die
  einzige Speicherzeile, summiert die gespeicherten Größen und speichert erst dann
  die Datei. Zwei parallele Uploads, die einzeln passen, aber nicht zusammen,
  laufen nacheinander, und der zweite wird abgelehnt. Ein Test spielt dieses
  Wettrennen unter PostgreSQL mit zwei Threads nach und schlägt fehl, sobald die
  Sperre entfernt wird.

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

  Die Verwaltung führt die ganze Hinzufügen- und Bearbeiten-Ansicht in einer
  Transaktion aus. Das Formular holt sich die Sperre daher in `clean()` und hält
  sie, bis die Datei gespeichert ist. Ein Kontingentfehler erscheint im Formular
  direkt am Dateifeld.
- **Der Katalogzustand steht in der URL.** Suche, Kategorie, Dateityp,
  Sortierung, Raster- oder Listenansicht, Seite und ausgewählte Datei sind
  Abfrageparameter. Links lassen sich teilen, die Seite übersteht ein Neuladen,
  und der Zurück-Knopf funktioniert. Ungültige Werte werden einzeln verworfen,
  statt die Seite scheitern zu lassen.
- **Alles funktioniert ohne JavaScript.** Links und Formulare erledigen alles,
  auch das Detailfenster, die Sprach- und Designmenüs und die Vollbildansicht
  (CSS `:target`). Ein Skript mit 40 Zeilen ergänzt nur die Tasten Esc und `/`
  und schließt Menüs bei einem Klick daneben.
- **Der Typ wird am Inhalt erkannt.** Ob eine Datei ein Bild ist, entscheidet
  Pillow. Ein in `.png` umbenanntes PDF wird also nicht als Bild angezeigt.
  Vorschaubilder beachten die EXIF-Drehung, übergroße Bilder
  (Dekompressionsbomben) werden übersprungen.
- **Dateien auf der Platte folgen der Datenbank.** Beim Ersetzen oder Löschen
  verschwinden die alte Datei und ihr Vorschaubild erst nach dem Commit der
  Transaktion. Ein Rollback hinterlässt nie eine Zeile, die ins Leere zeigt.
- **Die Suche ignoriert Groß- und Kleinschreibung und „ё“ und nutzt einen
  Index.** Jede Datei speichert Titel, Beschreibung und Dateinamen in
  Kleinbuchstaben, mit е statt ё, und die Suchanfrage wird genauso umgewandelt.
  `Ёлка` findet also `ёлка` und `елка`. Die Teilstringsuche läuft über einen
  Trigramm-GIN-Index (`pg_trgm`), und ein Test prüft, dass der Abfrageplan ihn
  verwendet.
- **Bestehende Daten werden migriert.** Eine Datenmigration ergänzt Größen, Typen
  und Vorschaubilder für Dateien von vor der Überarbeitung und benennt doppelte
  Kategorien um, bevor der Name eindeutig wird. Ein Test führt sie mit Daten des
  Prototyps aus.

### Sicherheit

- Hochgeladene Dateien haben keine öffentliche URL, sie werden von Views
  ausgeliefert. Downloads kommen mit `Content-Disposition: attachment` und dem
  Originalnamen, und im Browser werden nur Rasterbilder direkt angezeigt. Eine
  hochgeladene SVG- oder HTML-Datei kann daher keine Skripte auf der Seite
  ausführen.
- Eine strenge Content Security Policy (`script-src 'self'`, keine Inline-Skripte
  oder -Styles, keine fremden Domains) auf allen Seiten, die Verwaltung
  eingeschlossen. Der Smoke-Test schlägt bei jeder CSP-Verletzung in der
  Browserkonsole fehl.
- Im Produktivbetrieb startet die App nicht ohne `DJANGO_SECRET_KEY`.
  `check --deploy` läuft ohne Warnungen durch (HSTS, HTTPS-Weiterleitung, sichere
  Cookies, `X-Frame-Options: DENY`). Der Health Check ist von der
  HTTPS-Weiterleitung ausgenommen, damit die Containerprüfung hinter einem Proxy
  funktioniert.
- Das Image läuft ohne Root-Rechte und installiert nur Wheels.
- Der Superuser aus `ADMIN_USERNAME` und `ADMIN_PASSWORD` wird einmal angelegt.
  Ein in der Verwaltung geändertes Passwort wird beim nächsten Neustart nicht
  mehr zurückgesetzt.
- Das Demokonto darf Dateien und Kategorien verwalten, aber keine Benutzer.

### Lokalisierung

- Die Quelltexte sind englisch, dazu kommen russische, französische und deutsche
  gettext-Kataloge in `locale/`, einschließlich Pluralformen („2 Dateien“,
  „2 fichiers“, „5 файлов“) und Modellnamen in der Verwaltung.
- Die Sprache kommt aus einem Cookie, das das Sprachmenü setzt, sonst aus dem
  Browser. Datumsangaben und Dateigrößen folgen der Sprache („3. Oktober 2026“
  und „Oct. 3, 2026“, „35,2 KB“ und „35.2 KB“).
- Die CI prüft, ob die kompilierten `.mo`-Kataloge zu den `.po`-Quellen passen.

### Architektur

```mermaid
flowchart LR
    V[Besucher] -->|GET, Zustand in der URL| C[Katalog-Views]
    S[Mitarbeitende] -->|Upload| A[Django admin]
    A -->|clean, Sperre der Speicherzeile| Q[services.reserve_space]
    A --> M[File.save]
    M -->|Pillow| T[media.inspect<br/>Typ, Größe, Vorschau]
    M --> DB[(PostgreSQL)]
    M --> FS[/Datei-Volume/]
    C -->|höchstens 7 Abfragen| DB
    C -->|Auslieferung mit sicheren Headern| FS
```

| Modul | Aufgabe |
|---|---|
| `catalog/views.py` | Katalogseite, Vorschaubilder, Ansicht und Download von Dateien, Design, Health Check |
| `catalog/models.py` | Kategorien, Dateien mit gespeicherten Metadaten, die Speicherzeile |
| `catalog/services.py` | Kontingentprüfung unter Zeilensperre, Uploads, Speicherübersicht |
| `catalog/media.py` | Typerkennung am Inhalt, Vorschaubilder, Aufräumen von Dateien |
| `catalog/admin.py` | Uploadformular mit Kontingent- und Größenprüfung, Vorschaubilder in Listen |
| `catalog/demo.py`, `seed_demo` | Generierte Demobilder, Dokumente, Audio und Archive |
| `docker/smoke_test.py` | Rundgang im Browser durch Katalog und Verwaltung |

### Was die Überarbeitung geändert hat

Das Projekt begann als Prototyp für eine einzelne Bibliothek. Um daraus ein
gepflegtes Produkt zu machen, waren nötig

- Metadaten und Vorschaubilder speichern, statt Dateien bei jeder Anfrage zu
  lesen, mit einer Datenmigration für bestehende Zeilen;
- das Kontingent unter einer Zeilensperre durchsetzen und Kategorien mit Dateien
  schützen;
- Suche, Filter, Sortierung und Seitenaufteilung auf den Server verlagern, mit
  dem ganzen Zustand in der URL;
- Dateien über Views statt über einen öffentlichen Ordner ausliefern und eine CSP
  einführen;
- die CDNs von Tailwind und den Symbolen durch handgeschriebenes CSS und ein
  SVG-Sprite ersetzen, django-jet durch die Standardverwaltung;
- die russische, französische und deutsche Übersetzung, das dunkle Design und das
  Smartphone-Layout ergänzen;
- Einstellungen in Umgebungsvariablen verlagern und auf Django 6.1, Python 3.13
  und PostgreSQL 17 aktualisieren;
- Tests, Docker, eine CI mit Smoke-Test im Browser, Demodaten und Releases
  hinzufügen.

## Screenshots

| Detailfenster | Vollbildansicht |
|---|---|
| ![Details](docs/screenshots/de/details.png) | ![Vollbild](docs/screenshots/de/zoom.png) |

| Liste mit einem Dokument | Dunkles Design |
|---|---|
| ![Liste](docs/screenshots/de/list.png) | ![Dunkles Design](docs/screenshots/de/dark.png) |

| Smartphone | Smartphone, Details |
|---|---|
| ![Smartphone](docs/screenshots/de/mobile.png) | ![Details auf dem Smartphone](docs/screenshots/de/mobile-details.png) |

| Dateiliste in der Verwaltung | Anmeldung mit dem Demokonto |
|---|---|
| ![Dateien](docs/screenshots/de/admin-files.png) | ![Anmeldung](docs/screenshots/de/admin-login.png) |

## Ohne Docker starten

Benötigt werden Python 3.12 oder neuer und PostgreSQL. Die Datenbank aus der
Compose-Datei ist auf `localhost` erreichbar und passt zur Standard-`DATABASE_URL`.

```bash
docker compose up --detach db  # PostgreSQL on localhost:5432
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=True DEMO_USERNAME=demo DEMO_PASSWORD=demo12345
python manage.py migrate
python manage.py seed_demo     # Demodaten und Demokonto, optional
python manage.py runserver
```

## Konfiguration

Die Einstellungen kommen aus Umgebungsvariablen oder einer `.env`-Datei. Ein
kommentiertes Beispiel für den Produktivbetrieb steht in
[`.env.example`](.env.example).

| Variable | Zweck | Standard |
|---|---|---|
| `DJANGO_SECRET_KEY` | Geheimer Schlüssel, Pflicht bei `DJANGO_DEBUG=False` | ein fester Schlüssel im Debug-Modus |
| `DJANGO_DEBUG` | Debug-Modus | `False` |
| `DJANGO_ALLOWED_HOSTS` | Hostnamen, durch Kommas getrennt | `localhost` im Debug-Modus |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Herkünfte, die Formulare senden dürfen | keine |
| `DJANGO_TIME_ZONE` | Zeitzone für Datumsangaben | `UTC` |
| `DATABASE_URL` | PostgreSQL-Datenbank, zum Beispiel `postgres://user:pass@host/db` | `postgres://library:library@localhost:5432/library` |
| `DATABASE_PORT` | Port der Compose-Datenbank auf `localhost` | `5432` |
| `MEDIA_ROOT` | Ordner für hochgeladene Dateien | `./media` |
| `STORAGE_QUOTA_BYTES` | Anfangskontingent für alle Dateien, `0` für unbegrenzt, danach in der Verwaltung änderbar | 50 GB |
| `FILE_UPLOAD_MAX_BYTES` | Grenze für eine Datei | 512 MB |
| `CATALOG_PAGE_SIZE` | Dateien pro Katalogseite | `24` |
| `HTTPS` | HTTPS-Weiterleitung, HSTS und sichere Cookies | an, außer im Debug-Modus |
| `USE_X_FORWARDED_PROTO` | `X-Forwarded-Proto` eines TLS-Proxys vertrauen | `False` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Superuser, der beim Start angelegt wird, falls er fehlt | keiner |
| `DEMO_SEED` | Leere Mediathek beim Start mit Demodaten füllen (Docker) | `False`, `True` in compose |
| `DEMO_USERNAME`, `DEMO_PASSWORD` | Demokonto, wird auf der Anmeldeseite angezeigt | keines |
| `LOG_LEVEL` | Log-Level | `INFO` |

`python manage.py seed_demo --reset` löscht alle Dateien und Kategorien und legt
die Demodaten neu an.

## Tests

```bash
# die Tests brauchen PostgreSQL, die Datenbank aus compose genügt
docker compose up --detach db
ruff check . && ruff format --check .
coverage run manage.py test --settings=virtual_library.settings_test && coverage report

# Smoke-Test im Browser und Screenshots gegen einen laufenden Stack
docker compose up --build --detach --wait
python -m playwright install chromium
python docker/smoke_test.py
python scripts/screenshots.py
```

70 Tests mit 99 % Abdeckung, die Schwelle in der CI liegt bei 90 %. Die CI
führt sie unter PostgreSQL 17 mit Python 3.12 und 3.13 aus, einschließlich des
Wettrennens paralleler Uploads und der Prüfung, dass die Suche den
Trigramm-Index nutzt. Außerdem prüft sie Migrationen, Übersetzungen und die
Produktiveinstellungen, baut dann das Image, startet den Stack und lässt den
Smoke-Test im Browser laufen. Er lädt eine Datei über die Verwaltung hoch,
löscht sie wieder und schlägt bei jedem Fehler in der Konsole fehl.

## Projektstruktur

```
├── catalog/
│   ├── management/commands/   # seed_demo, ensure_admin
│   ├── migrations/
│   ├── static/catalog/        # CSS, SVG-Symbole, ein kleines Skript
│   ├── templates/catalog/
│   ├── tests/
│   ├── admin.py  media.py  models.py  services.py  views.py
├── locale/                    # russische, französische und deutsche Übersetzung
├── templates/                 # 404-Seite, Anmeldung zur Verwaltung
├── virtual_library/           # Einstellungen und URLs
├── docker/                    # Entrypoint und Smoke-Test
├── scripts/screenshots.py
├── docs/screenshots/
├── Dockerfile
├── docker-compose.yml
└── .github/                   # CI, Releases, Dependabot
```

## Lizenz

[PolyForm Noncommercial 1.0.0](LICENSE). Nutzung, Änderung und Weitergabe sind
für nichtkommerzielle Zwecke erlaubt, sofern der Hinweis
`Copyright (c) 2026 DogNellaf` erhalten bleibt. Für kommerzielle Nutzung ist eine
eigene Lizenz nötig, wenden Sie sich an [DogNellaf](https://github.com/DogNellaf).
