from unittest import mock

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from catalog.models import File
from catalog.tests.factories import TempMediaMixin, make_category, make_file, png_bytes


def titles(response) -> list[str]:
    return [file.title for file in response.context["page"].object_list]


class CatalogTests(TempMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.photos = make_category("Photos")
        cls.docs = make_category("Documents")
        cls.sunset = make_file(cls.photos, "Sunset", content=png_bytes(), description="Evening sky")
        cls.tree = make_file(cls.photos, "Ёлка", name="tree.png")
        cls.report = make_file(cls.docs, "Annual report", name="report.pdf", content=b"x" * 5000)
        cls.notes = make_file(cls.docs, "notes", name="notes.txt", content=b"x" * 10)

    def get(self, **params):
        return self.client.get(reverse("index"), params)

    def test_lists_all_files_with_counts(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(titles(response), ["notes", "Annual report", "Ёлка", "Sunset"])
        self.assertEqual(response.context["total_count"], 4)
        counts = {c.name: c.files_count for c in response.context["categories"]}
        self.assertEqual(counts, {"Documents": 2, "Photos": 2})
        self.assertContains(response, reverse("file_thumbnail", args=[self.sunset.pk]))
        self.assertNotContains(response, "/media/")

    def test_filters_by_category_and_kind(self):
        self.assertEqual(titles(self.get(category=self.photos.pk)), ["Ёлка", "Sunset"])
        self.assertEqual(titles(self.get(kind="document")), ["notes", "Annual report"])
        response = self.get(category=self.docs.pk)
        self.assertEqual(response.context["category"], self.docs)
        self.assertEqual([k for k, _label, _n in response.context["kinds"]], ["document"])

    def test_search_ignores_case_and_yo_on_every_database(self):
        self.assertEqual(titles(self.get(q="ЕЛКА")), ["Ёлка"])
        self.assertEqual(titles(self.get(q="evening")), ["Sunset"])
        self.assertEqual(titles(self.get(q="report.pdf")), ["Annual report"])
        response = self.get(q="nothing like this")
        self.assertContains(response, "Nothing matches these filters.")

    def test_sorting(self):
        self.assertEqual(
            titles(self.get(sort="name")), ["Annual report", "notes", "Sunset", "Ёлка"]
        )
        self.assertEqual(titles(self.get(sort="-name"))[0], "Ёлка")
        self.assertEqual(titles(self.get(sort="old"))[0], "Sunset")
        self.assertEqual(titles(self.get(sort="-size"))[0], "Annual report")
        self.assertEqual(titles(self.get(sort="size"))[0], "notes")

    def test_invalid_parameters_are_ignored(self):
        response = self.get(sort="drop table", kind="virus", category="abc", view="3d", file="x")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(titles(response)), 4)
        self.assertEqual((response.context["sort"], response.context["view"]), ("new", "grid"))

    def test_state_is_kept_in_links(self):
        response = self.get(category=self.photos.pk, sort="name", view="list")
        self.assertContains(response, 'class="files list"')
        self.assertContains(
            response, f"?category={self.photos.pk}&amp;sort=name&amp;view=list&amp;file="
        )

    @override_settings(CATALOG_PAGE_SIZE=3)
    def test_pagination(self):
        response = self.get(page=2)
        self.assertEqual(titles(response), ["Sunset"])
        self.assertContains(response, "Page 2 of 2")
        self.assertEqual(titles(self.get(page=99)), ["Sunset"])

    def test_details_panel(self):
        response = self.get(file=self.sunset.pk)
        self.assertEqual(response.context["selected"], self.sunset)
        self.assertContains(response, "120 × 80 px")
        self.assertContains(response, reverse("file_download", args=[self.sunset.pk]))
        self.assertContains(response, reverse("file_preview", args=[self.sunset.pk]))
        self.assertNotContains(response, "admin/catalog/file/")
        self.assertIsNone(self.get(file=999999).context["selected"])
        response = self.get(file=self.report.pk)
        self.assertContains(response, "No description.")
        self.assertNotContains(response, 'id="zoom"')

    def test_query_count_does_not_grow_with_files(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(self.get(file=self.sunset.pk).status_code, 200)
            return len(queries)

        count_queries()  # The first request creates the storage row.
        before = count_queries()
        for i in range(10):
            make_file(self.photos, f"Extra {i}", content=b"x")
        self.assertEqual(count_queries(), before)
        self.assertLessEqual(before, 7)

    def test_empty_library(self):
        File.objects.all().delete()
        response = self.get()
        self.assertContains(response, "The library is empty.")

    def test_legacy_category_url_redirects(self):
        response = self.client.get(f"/category/{self.docs.pk}")
        self.assertRedirects(response, f"/?category={self.docs.pk}", status_code=301)

    def test_russian_interface(self):
        self.client.post(reverse("set_language"), {"language": "ru", "next": "/"})
        response = self.get()
        self.assertContains(response, '<html lang="ru"')
        self.assertContains(response, "4 файла")
        self.assertContains(response, "Сначала новые")

    def test_unknown_page_uses_the_library_template(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Back to the library", status_code=404)

    def test_security_headers(self):
        response = self.get()
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")


class FileEndpointTests(TempMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        category = make_category()
        cls.image = make_file(category, "Photo", name="фото заката.png")
        cls.pdf = make_file(category, "Report", name="report.pdf", content=b"%PDF-1.4 data")
        cls.svg = make_file(category, "Logo", name="logo.svg", content=b"<svg></svg>")

    def test_download_is_an_attachment_with_the_original_name(self):
        response = self.client.get(reverse("file_download", args=[self.image.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.image.file.open("rb").read())
        disposition = response["Content-Disposition"]
        self.assertTrue(disposition.startswith("attachment;"))
        self.assertIn("filename*=utf-8''%D1%84%D0%BE%D1%82%D0%BE", disposition)

    def test_svg_is_downloaded_never_shown(self):
        response = self.client.get(reverse("file_download", args=[self.svg.pk]))
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        preview = self.client.get(reverse("file_preview", args=[self.svg.pk]))
        self.assertEqual(preview.status_code, 404)

    def test_preview_shows_only_images(self):
        response = self.client.get(reverse("file_preview", args=[self.image.pk]))
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        self.assertEqual(
            self.client.get(reverse("file_preview", args=[self.pdf.pk])).status_code, 404
        )

    def test_thumbnail(self):
        response = self.client.get(reverse("file_thumbnail", args=[self.image.pk]))
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertIn("max-age", response["Cache-Control"])
        etag = response["ETag"]
        cached = self.client.get(
            reverse("file_thumbnail", args=[self.image.pk]), headers={"if-none-match": etag}
        )
        self.assertEqual(cached.status_code, 304)
        self.assertEqual(
            self.client.get(reverse("file_thumbnail", args=[self.pdf.pk])).status_code, 404
        )
        self.assertEqual(self.client.get(reverse("file_thumbnail", args=[999])).status_code, 404)

    def test_missing_file_on_disk_is_a_404(self):
        lost = make_file(self.pdf.category, "Lost", name="lost.pdf", content=b"data")
        lost.file.storage.delete(lost.file.name)
        response = self.client.get(reverse("file_download", args=[lost.pk]))
        self.assertEqual(response.status_code, 404)

    def test_broken_image_on_disk_is_a_404(self):
        broken = make_file(self.image.category, "Broken", name="broken.png")
        with open(broken.file.path, "wb") as handle:
            handle.write(b"garbage")
        response = self.client.get(reverse("file_preview", args=[broken.pk]))
        self.assertEqual(response.status_code, 404)

    def test_only_get(self):
        self.assertEqual(
            self.client.post(reverse("file_download", args=[self.pdf.pk])).status_code, 405
        )


class ThemeAndHealthTests(TestCase):
    def test_theme_cookie(self):
        response = self.client.post(reverse("set_theme"), {"theme": "dark", "next": "/?view=list"})
        self.assertRedirects(response, "/?view=list", fetch_redirect_response=False)
        self.assertEqual(response.cookies["theme"].value, "dark")
        page = self.client.get("/")
        self.assertContains(page, 'data-theme="dark"')

        response = self.client.post(reverse("set_theme"), {"theme": "auto"})
        self.assertEqual(response.cookies["theme"].value, "")
        self.assertContains(self.client.get("/"), 'data-theme="auto"')

    def test_theme_refuses_open_redirects(self):
        response = self.client.post(
            reverse("set_theme"), {"theme": "light", "next": "https://evil.example/"}
        )
        self.assertEqual(response["Location"], "/")

    def test_favicon(self):
        response = self.client.get("/favicon.ico")
        self.assertRedirects(
            response, "/static/catalog/favicon.svg", status_code=301, fetch_redirect_response=False
        )

    def test_health(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("no-cache", response["Cache-Control"])

    def test_health_reports_a_broken_database(self):
        with mock.patch("catalog.views.connection.cursor", side_effect=RuntimeError("down")):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_health_is_exempt_from_the_https_redirect(self):
        self.assertEqual(self.client.get(reverse("health")).status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 301)
