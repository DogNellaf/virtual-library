import re

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, File, Storage
from catalog.tests.factories import TempMediaMixin, make_file, png_bytes


class AdminTests(TempMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("admin", "a@example.com", "pw")
        cls.file = make_file(title="Sunset")
        cls.category = cls.file.category

    def setUp(self):
        self.client.force_login(self.admin)

    def upload(self, **overrides):
        data = {
            "title": "New poster",
            "category": self.category.pk,
            "description": "",
            "file": SimpleUploadedFile("poster.png", png_bytes()),
        }
        data.update(overrides)
        return self.client.post(reverse("admin:catalog_file_add"), data)

    def test_every_admin_page_opens(self):
        index = self.client.get(reverse("admin:index"))
        self.assertEqual(index.status_code, 200)
        links = set(re.findall(r'href="(/admin/[^"]+/)"', index.content.decode()))
        links |= {
            reverse("admin:catalog_file_change", args=[self.file.pk]),
            reverse("admin:catalog_category_change", args=[self.category.pk]),
            reverse("admin:catalog_storage_change", args=[1]),
            reverse("admin:catalog_file_changelist") + "?q=sun&kind__exact=image",
        }
        for link in sorted(links):
            with self.subTest(link=link):
                self.assertEqual(self.client.get(link).status_code, 200)

    def test_changelist_shows_thumbnails_and_sizes(self):
        response = self.client.get(reverse("admin:catalog_file_changelist"))
        self.assertContains(response, reverse("file_thumbnail", args=[self.file.pk]))
        self.assertContains(response, "catalog/admin.css")
        response = self.client.get(reverse("admin:catalog_category_changelist"))
        self.assertContains(response, f"?category__id__exact={self.category.pk}")

    def test_upload(self):
        response = self.upload()
        self.assertRedirects(response, reverse("admin:catalog_file_changelist"))
        file = File.objects.get(title="New poster")
        self.assertEqual((file.kind, file.original_name), ("image", "poster.png"))
        page = self.client.get(reverse("admin:catalog_file_change", args=[file.pk]))
        self.assertContains(page, "120 × 80 px")
        self.assertContains(page, f'href="{reverse("file_download", args=[file.pk])}"')
        self.assertNotContains(page, "/media/")

    def test_upload_over_quota_is_rejected_in_the_form(self):
        Storage.load()
        Storage.objects.update(quota_bytes=self.file.size + 10)
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Not enough space")
        self.assertFalse(File.objects.filter(title="New poster").exists())

    def test_editing_without_a_new_file_skips_the_quota(self):
        Storage.load()
        Storage.objects.update(quota_bytes=1)
        url = reverse("admin:catalog_file_change", args=[self.file.pk])
        response = self.client.post(
            url, {"title": "Renamed", "category": self.category.pk, "description": "note"}
        )
        self.assertEqual(response.status_code, 302)
        self.file.refresh_from_db()
        self.assertEqual((self.file.title, self.file.title_key), ("Renamed", "renamed"))

    @override_settings(FILE_UPLOAD_MAX_BYTES=100)
    def test_upload_size_limit(self):
        response = self.upload()
        self.assertContains(response, "The file is too large. The limit is 100")

    def test_category_with_files_is_protected(self):
        url = reverse("admin:catalog_category_delete", args=[self.category.pk])
        response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_storage_is_a_single_row(self):
        Storage.load()
        self.assertEqual(self.client.get(reverse("admin:catalog_storage_add")).status_code, 403)
        response = self.client.post(
            reverse("admin:catalog_storage_change", args=[1]), {"quota_bytes": 0}
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(
            self.client.get(reverse("admin:catalog_storage_changelist")), "No limit"
        )

    def test_view_on_site_opens_the_details_panel(self):
        response = self.client.get(
            reverse("admin:view_on_site", args=[self.file_content_type(), self.file.pk])
        )
        self.assertTrue(response["Location"].endswith(f"/?file={self.file.pk}"))

    def file_content_type(self):
        from django.contrib.contenttypes.models import ContentType

        return ContentType.objects.get_for_model(File).pk

    def test_staff_sees_edit_link_in_the_catalog(self):
        response = self.client.get("/", {"file": self.file.pk})
        self.assertContains(response, reverse("admin:catalog_file_change", args=[self.file.pk]))


class DemoAccountTests(TempMediaMixin, TestCase):
    def test_login_page_shows_the_demo_account(self):
        response = self.client.get(reverse("admin:login"))
        self.assertContains(response, "Demo account <strong>demo</strong>")

    def test_demo_user_can_manage_files_but_not_users(self):
        call_command("seed_demo", stdout=open("/dev/null", "w"))  # noqa: SIM115
        self.assertTrue(self.client.login(username="demo", password="demo12345"))
        self.assertEqual(self.client.get(reverse("admin:catalog_file_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:auth_user_changelist")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("admin:catalog_storage_changelist")).status_code, 200
        )
