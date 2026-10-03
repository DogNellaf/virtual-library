"""Settings for the test suite: the production settings with a fixed key and fast hashing."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-used-anywhere-else")
os.environ.setdefault("HTTPS", "False")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost")
os.environ["DEMO_USERNAME"] = "demo"
os.environ["DEMO_PASSWORD"] = "demo12345"  # noqa: S105

from virtual_library.settings import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}  # noqa: F405
LOGGING["root"]["level"] = "CRITICAL"  # noqa: F405
