import io
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.models import Category, File
from catalog.tests.factories import TempMediaMixin


def run(*args, **env) -> str:
    out = io.StringIO()
    with mock.patch.dict(os.environ, env):
        call_command(*args, stdout=out)
    return out.getvalue()


class SeedDemoTests(TempMediaMixin, TestCase):
    def test_seeds_once_and_resets(self):
        self.assertIn("Added 28 demo files", run("seed_demo"))
        kinds = set(File.objects.values_list("kind", flat=True))
        self.assertEqual(kinds, {"image", "document", "spreadsheet", "archive", "audio"})
        self.assertEqual(Category.objects.count(), 5)
        self.assertTrue(all(f.thumbnail for f in File.objects.filter(kind="image")))
        self.assertEqual(
            File.objects.order_by("-upload_date", "-id").first().title, "Morning in the valley"
        )

        self.assertIn("nothing to seed", run("seed_demo"))
        self.assertEqual(File.objects.count(), 28)

        File.objects.filter(category__name="Audio").delete()
        self.assertIn("Added 28", run("seed_demo", "--reset"))

    @override_settings(DEMO_USERNAME="", DEMO_PASSWORD="")
    def test_no_demo_user_without_settings(self):
        run("seed_demo")
        self.assertFalse(get_user_model().objects.exists())


class EnsureAdminTests(TestCase):
    def test_creates_keeps_and_resets(self):
        env = {"ADMIN_USERNAME": "librarian", "ADMIN_PASSWORD": "first-password"}
        self.assertIn("Created superuser", run("ensure_admin", **env))
        user = get_user_model().objects.get(username="librarian")
        self.assertTrue(user.is_superuser and user.is_staff)

        user.set_password("changed-in-admin")
        user.save()
        self.assertIn("password kept", run("ensure_admin", **env))
        user.refresh_from_db()
        self.assertTrue(user.check_password("changed-in-admin"))

        self.assertIn("Password reset", run("ensure_admin", "--reset-password", **env))
        user.refresh_from_db()
        self.assertTrue(user.check_password("first-password"))

    def test_skips_without_variables(self):
        self.assertIn("skipping", run("ensure_admin", ADMIN_USERNAME="", ADMIN_PASSWORD=""))
        self.assertFalse(get_user_model().objects.exists())
