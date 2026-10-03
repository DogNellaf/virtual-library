# Médiathèque

> [🇬🇧 English](README.md) | [🇷🇺 Русский](README.ru.md) | 🇫🇷 Français | [🇩🇪 Deutsch](README.de.md)

[![CI](https://github.com/DogNellaf/virtual-library/actions/workflows/ci.yml/badge.svg)](https://github.com/DogNellaf/virtual-library/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/DogNellaf/virtual-library)](https://github.com/DogNellaf/virtual-library/releases)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB)
![Django](https://img.shields.io/badge/django-6.1-092E20)
![PostgreSQL](https://img.shields.io/badge/postgresql-17-4169E1)
![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-orange)

Une médiathèque pour une bibliothèque publique. Le personnel ajoute des images,
des documents et d’autres fichiers dans l’administration et les range par
catégories. Les visiteurs parcourent le catalogue, y font des recherches,
affichent les images et téléchargent les fichiers. L’interface existe en
anglais, russe, français et allemand, avec un thème sombre et une mise en page
pour téléphone.

![Catalogue](docs/screenshots/fr/catalog.png)

## Démarrage rapide

```bash
docker compose up --build
```

Ouvrez <http://localhost:8000>. La pile démarre PostgreSQL et l’application, puis
remplit la médiathèque avec 28 fichiers générés dans 5 catégories. Pour ajouter
des fichiers, cliquez sur **Gérer** et connectez-vous avec **demo / demo12345**.
En démonstration, le quota de stockage est de 25 Mo et un fichier ne peut pas
dépasser 10 Mo.

## Étude de cas

### Problème

La bibliothèque avait un prototype qui fonctionnait. Il affichait les fichiers en
grille et permettait au personnel de les ajouter dans l’administration. Derrière,
il y avait des problèmes qui n’apparaissent qu’à l’usage réel.

- Pour dessiner la barre de stockage, chaque chargement de page ouvrait chaque
  fichier sur le disque.
- Tous les fichiers étaient affichés d’un coup et filtrés dans le navigateur.
- Le quota était seulement affiché. Rien n’empêchait un envoi qui ne tenait pas.
- Les tailles de fichiers étaient divisées par 8, la barre de stockage montrait
  une fraction au lieu d’un pourcentage et plantait sans quota, et les compteurs
  de la barre latérale restaient vides.
- Avec `DEBUG=False`, ni les fichiers statiques ni les fichiers envoyés
  n’étaient servis.
- Supprimer une catégorie supprimait en silence tous ses fichiers.

### Solution

Tout ce dont le catalogue a besoin est calculé une seule fois, à l’envoi du
fichier, et enregistré avec lui.

| Enregistré à l’envoi | Utilisé pour |
|---|---|
| Taille en octets | La barre de stockage en une requête `SUM`, le contrôle du quota |
| Type (image, document, audio, etc.) | Le filtre par type et les icônes |
| Largeur et hauteur | Le panneau de détails |
| Miniature WebP jusqu’à 640 px | La grille charge un petit aperçu au lieu de la photo d’origine |
| Titre et texte en minuscules | Une recherche et un tri identiques sous SQLite et PostgreSQL |

La page du catalogue exécute au plus 7 requêtes SQL, que la médiathèque contienne
10 fichiers ou 10 000, et un test échoue si ce nombre augmente avec le nombre de
fichiers.

### Choix techniques

- **Le quota ne peut pas être dépassé.** Un envoi verrouille l’unique ligne de
  stockage, additionne les tailles enregistrées et seulement ensuite enregistre
  le fichier. Deux envois parallèles qui tiennent chacun seuls mais pas ensemble
  passent l’un après l’autre, et le second est refusé. Un test rejoue cette
  concurrence sous PostgreSQL avec deux threads et échoue dès qu’on retire le
  verrou.

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

  L’administration exécute toute la vue d’ajout et de modification dans une
  transaction, donc le formulaire prend le verrou dans `clean()` et le garde
  jusqu’à l’enregistrement du fichier. Une erreur de quota s’affiche dans le
  formulaire, à côté du champ du fichier.
- **L’état du catalogue est dans l’URL.** Recherche, catégorie, type de fichier,
  tri, affichage en grille ou en liste, page et fichier sélectionné sont des
  paramètres de requête. On peut partager un lien, la page survit à un
  rechargement et le bouton retour fonctionne. Les valeurs invalides sont
  ignorées une par une au lieu de casser la page.
- **Tout fonctionne sans JavaScript.** Les liens et les formulaires font tout le
  travail, y compris le panneau de détails, les menus de langue et de thème et
  l’affichage en taille réelle (CSS `:target`). Un script de 40 lignes ajoute
  seulement les raccourcis Échap et `/` et ferme les menus au clic extérieur.
- **Le type est reconnu par le contenu.** C’est Pillow qui décide si un fichier
  est une image, donc un PDF renommé en `.png` n’est pas affiché comme une image.
  Les miniatures respectent la rotation EXIF, et les images démesurées
  (bombes de décompression) sont ignorées.
- **Les fichiers sur le disque suivent la base.** Remplacer ou supprimer un
  fichier efface l’ancien fichier et sa miniature seulement après la validation
  de la transaction, et une annulation ne laisse jamais une ligne qui pointe
  vers rien.
- **La recherche ignore la casse et le « ё ».** SQLite ne gère la casse que pour
  l’ASCII, donc `Ёлка` ne correspondrait pas à `ёлка`. Chaque fichier garde une
  copie de son titre et de son texte en minuscules, avec ё remplacé par е, et la
  requête est transformée de la même façon.
- **Les données existantes sont migrées.** Une migration de données remplit les
  tailles, les types et les miniatures des fichiers envoyés avant la refonte et
  renomme les catégories en double avant que le nom ne devienne unique. Un test
  l’exécute sur des données du prototype.

### Sécurité

- Les fichiers envoyés n’ont pas d’URL publique, ils sont servis par des vues.
  Les téléchargements utilisent `Content-Disposition: attachment` avec le nom
  d’origine, et seules les images matricielles s’affichent dans le navigateur.
  Un fichier SVG ou HTML envoyé ne peut donc pas exécuter de script sur le site.
- Une Content Security Policy stricte (`script-src 'self'`, sans scripts ni
  styles en ligne, sans domaines tiers) sur toutes les pages, administration
  comprise. Le test de fumée échoue à la moindre violation de CSP dans la
  console du navigateur.
- En production, l’application refuse de démarrer sans `DJANGO_SECRET_KEY`.
  `check --deploy` passe sans avertissement (HSTS, redirection HTTPS, cookies
  sécurisés, `X-Frame-Options: DENY`). Le health check est exclu de la
  redirection HTTPS, donc le contrôle du conteneur fonctionne derrière un proxy.
- L’image tourne avec un utilisateur sans privilèges et n’installe que des wheels.
- Le superutilisateur défini par `ADMIN_USERNAME` et `ADMIN_PASSWORD` est créé une
  seule fois. Un mot de passe modifié dans l’administration n’est plus
  réinitialisé au redémarrage suivant.
- Le compte de démonstration peut gérer les fichiers et les catégories, mais pas
  les utilisateurs.

### Localisation

- Les chaînes source sont en anglais, avec des catalogues gettext russe,
  français et allemand dans `locale/`, formes du pluriel comprises
  (« 2 fichiers », « 2 Dateien », « 5 файлов ») ainsi que les noms des modèles
  dans l’administration.
- La langue vient d’un cookie posé par le menu de langue, sinon du navigateur.
  Les dates et les tailles suivent la langue (« 3 octobre 2026 » et
  « Oct. 3, 2026 », « 35,2 Kio » et « 35.2 KB »).
- La CI vérifie que les catalogues `.mo` compilés correspondent aux sources `.po`.

### Architecture

```mermaid
flowchart LR
    V[Visiteur] -->|GET, état dans l’URL| C[Vues du catalogue]
    S[Personnel] -->|envoi| A[Django admin]
    A -->|clean, verrou de la ligne de stockage| Q[services.reserve_space]
    A --> M[File.save]
    M -->|Pillow| T[media.inspect<br/>type, taille, miniature]
    M --> DB[(PostgreSQL)]
    M --> FS[/Volume des fichiers/]
    C -->|au plus 7 requêtes| DB
    C -->|envoi avec en-têtes sûrs| FS
```

| Module | Rôle |
|---|---|
| `catalog/views.py` | Page du catalogue, miniatures, aperçus et téléchargements, thème, health check |
| `catalog/models.py` | Catégories, fichiers avec métadonnées enregistrées, ligne de stockage |
| `catalog/services.py` | Contrôle du quota sous verrou, envois, résumé du stockage |
| `catalog/media.py` | Détection du type par le contenu, miniatures, suppression des fichiers |
| `catalog/admin.py` | Formulaire d’envoi avec contrôle du quota et de la taille, miniatures dans les listes |
| `catalog/demo.py`, `seed_demo` | Images, documents, audio et archives de démonstration générés |
| `docker/smoke_test.py` | Parcours du catalogue et de l’administration dans un navigateur |

### Ce que la refonte a changé

Le projet est né comme prototype pour une seule bibliothèque. Pour en faire un
produit maintenu, il a fallu

- enregistrer les métadonnées et les miniatures au lieu de lire les fichiers à
  chaque requête, avec une migration de données pour les lignes existantes ;
- appliquer le quota sous un verrou de ligne et protéger les catégories qui
  contiennent des fichiers ;
- déplacer la recherche, les filtres, le tri et la pagination côté serveur, avec
  tout l’état dans l’URL ;
- servir les fichiers par des vues au lieu d’un dossier public, et ajouter une CSP ;
- remplacer les CDN de Tailwind et des icônes par du CSS écrit à la main et un
  sprite SVG, et django-jet par l’administration standard ;
- ajouter les traductions russe, française et allemande, le thème sombre et la
  mise en page pour téléphone ;
- passer les réglages en variables d’environnement et migrer vers Django 6.1,
  Python 3.13 et PostgreSQL 17 ;
- ajouter des tests, Docker, une CI avec test de fumée dans le navigateur, des
  données de démonstration et des releases.

## Captures d’écran

| Panneau de détails | Affichage en taille réelle |
|---|---|
| ![Détails](docs/screenshots/fr/details.png) | ![Taille réelle](docs/screenshots/fr/zoom.png) |

| Liste avec un document | Thème sombre |
|---|---|
| ![Liste](docs/screenshots/fr/list.png) | ![Thème sombre](docs/screenshots/fr/dark.png) |

| Téléphone | Téléphone, détails |
|---|---|
| ![Téléphone](docs/screenshots/fr/mobile.png) | ![Détails sur téléphone](docs/screenshots/fr/mobile-details.png) |

| Liste des fichiers dans l’administration | Connexion avec le compte de démonstration |
|---|---|
| ![Fichiers](docs/screenshots/fr/admin-files.png) | ![Connexion](docs/screenshots/fr/admin-login.png) |

## Lancer sans Docker

Il faut Python 3.12 ou plus récent. Sans `DATABASE_URL`, un fichier SQLite local
est utilisé.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=True DEMO_USERNAME=demo DEMO_PASSWORD=demo12345
python manage.py migrate
python manage.py seed_demo     # données et compte de démonstration, facultatif
python manage.py runserver
```

## Configuration

Les réglages viennent des variables d’environnement ou d’un fichier `.env`.
[`.env.example`](.env.example) contient un exemple commenté pour la production.

| Variable | Rôle | Par défaut |
|---|---|---|
| `DJANGO_SECRET_KEY` | Clé secrète, obligatoire avec `DJANGO_DEBUG=False` | une clé fixe en mode debug |
| `DJANGO_DEBUG` | Mode debug | `False` |
| `DJANGO_ALLOWED_HOSTS` | Noms d’hôtes séparés par des virgules | `localhost` en mode debug |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origines autorisées à envoyer des formulaires | aucune |
| `DJANGO_TIME_ZONE` | Fuseau horaire des dates | `UTC` |
| `DATABASE_URL` | Base de données, par exemple `postgres://user:pass@host/db` | SQLite dans `db.sqlite3` |
| `MEDIA_ROOT` | Dossier des fichiers envoyés | `./media` |
| `STORAGE_QUOTA_BYTES` | Quota initial pour tous les fichiers, `0` sans limite, modifiable ensuite dans l’administration | 50 Go |
| `FILE_UPLOAD_MAX_BYTES` | Limite pour un fichier | 512 Mo |
| `CATALOG_PAGE_SIZE` | Fichiers par page du catalogue | `24` |
| `HTTPS` | Redirection HTTPS, HSTS et cookies sécurisés | activé hors mode debug |
| `USE_X_FORWARDED_PROTO` | Faire confiance à `X-Forwarded-Proto` d’un proxy TLS | `False` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Superutilisateur créé au démarrage s’il n’existe pas | aucun |
| `DEMO_SEED` | Remplir une médiathèque vide avec la démonstration au démarrage (Docker) | `False`, `True` dans compose |
| `DEMO_USERNAME`, `DEMO_PASSWORD` | Compte de démonstration, affiché sur la page de connexion | aucun |
| `LOG_LEVEL` | Niveau de journalisation | `INFO` |

`python manage.py seed_demo --reset` supprime tous les fichiers et catégories et
recrée les données de démonstration.

## Tests

```bash
ruff check . && ruff format --check .
coverage run manage.py test --settings=virtual_library.settings_test && coverage report

# sous PostgreSQL, avec le test des envois parallèles
DATABASE_URL=postgres://postgres:postgres@localhost:5432/library \
  python manage.py test --settings=virtual_library.settings_test

# test de fumée dans le navigateur et captures sur une pile lancée
docker compose up --build --detach --wait
python -m playwright install chromium
python docker/smoke_test.py
python scripts/screenshots.py
```

68 tests, couverture de 99 %, seuil de 90 % en CI. La CI les lance sous SQLite et
PostgreSQL 17 avec Python 3.13 et sous SQLite avec Python 3.12, vérifie les
migrations, les traductions et les réglages de production, puis construit
l’image, démarre la pile et lance le test de fumée dans le navigateur. Il envoie
et supprime un fichier via l’administration et échoue à la moindre erreur dans
la console.

## Structure du projet

```
├── catalog/
│   ├── management/commands/   # seed_demo, ensure_admin
│   ├── migrations/
│   ├── static/catalog/        # CSS, icônes SVG, un petit script
│   ├── templates/catalog/
│   ├── tests/
│   ├── admin.py  media.py  models.py  services.py  views.py
├── locale/                    # traductions russe, française et allemande
├── templates/                 # page 404, connexion à l’administration
├── virtual_library/           # réglages et URL
├── docker/                    # entrypoint et test de fumée
├── scripts/screenshots.py
├── docs/screenshots/
├── Dockerfile
├── docker-compose.yml
└── .github/                   # CI, releases, Dependabot
```

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE). L’utilisation, la modification et la
redistribution sont autorisées à des fins non commerciales, à condition de
conserver la mention `Copyright (c) 2026 DogNellaf`. Un usage commercial demande
une licence séparée, contactez [DogNellaf](https://github.com/DogNellaf).
