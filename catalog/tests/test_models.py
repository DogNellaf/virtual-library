from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.test import TestCase, override_settings

from catalog.models import File, Storage, search_key
from catalog.tests.factories import TempMediaMixin, make_category, make_file, png_bytes


def stored(name: str) -> bool:
    return (Path(settings.MEDIA_ROOT) / name).exists()


class SearchKeyTests(TestCase):
    def test_folds_case_yo_and_spaces(self):
        self.assertEqual(search_key("  Ёлка   НОВОГОДНЯЯ "), "елка новогодняя")
        self.assertEqual(search_key("Straße"), "strasse")


class FileTests(TempMediaMixin, TestCase):
    def test_image_metadata_and_thumbnail(self):
        file = make_file(title="Sunset", name="sunset.png", content=png_bytes((1200, 800)))
        self.assertEqual(file.kind, File.Kind.IMAGE)
        self.assertEqual((file.width, file.height), (1200, 800))
        self.assertEqual(file.size, file.file.size)
        self.assertEqual(file.original_name, "sunset.png")
        self.assertEqual(file.extension, "PNG")
        self.assertTrue(file.is_image)
        self.assertTrue(file.thumbnail.name.endswith(".webp"))
        self.assertTrue(stored(file.thumbnail.name))
        with file.thumbnail.open("rb") as thumb:
            self.assertEqual(thumb.read(4), b"RIFF")

    def test_kind_comes_from_content_not_extension(self):
        fake = make_file(name="fake.png", content=b"not an image")
        self.assertEqual(fake.kind, File.Kind.OTHER)
        self.assertFalse(fake.thumbnail)
        renamed = make_file(name="scan.pdf", content=png_bytes())
        self.assertEqual(renamed.kind, File.Kind.IMAGE)

    def test_svg_is_never_an_image(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        file = make_file(name="logo.svg", content=svg)
        self.assertEqual(file.kind, File.Kind.OTHER)
        self.assertFalse(file.is_image)

    def test_documents_by_extension(self):
        cases = {
            "report.pdf": "document",
            "data.xlsx": "spreadsheet",
            "talk.pptx": "presentation",
            "song.mp3": "audio",
            "clip.mp4": "video",
            "backup.zip": "archive",
            "x.bin": "other",
        }
        category = make_category()
        for name, kind in cases.items():
            with self.subTest(name=name):
                self.assertEqual(make_file(category, name=name, content=b"data").kind, kind)

    def test_search_fields_follow_title_and_description(self):
        file = make_file(title="Ёжик в тумане", description="Мультфильм")
        self.assertEqual(file.title_key, "ежик в тумане")
        self.assertIn("мультфильм", file.search_text)
        self.assertIn("photo.png", file.search_text)
        file.title = "Hedgehog"
        file.save(update_fields=["title"])
        file.refresh_from_db()
        self.assertEqual(file.title_key, "hedgehog")

    def test_replacing_the_file_removes_the_old_one_after_commit(self):
        file = make_file()
        old_file, old_thumb = file.file.name, file.thumbnail.name
        file.file = SimpleUploadedFile("notes.txt", b"plain text")
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            file.save()
        self.assertEqual(len(callbacks), 1)
        self.assertFalse(stored(old_file))
        self.assertFalse(stored(old_thumb))
        self.assertTrue(stored(file.file.name))
        self.assertEqual((file.kind, file.thumbnail.name, file.width), ("document", None, None))

    def test_deleting_removes_stored_files(self):
        file = make_file()
        names = [file.file.name, file.thumbnail.name]
        with self.captureOnCommitCallbacks(execute=True):
            file.delete()
        self.assertFalse(any(stored(name) for name in names))

    def test_category_with_files_cannot_be_deleted(self):
        file = make_file()
        with self.assertRaises(ProtectedError):
            file.category.delete()

    def test_strings_and_urls(self):
        file = make_file(title="Sunset")
        self.assertEqual(str(file), "Sunset")
        self.assertEqual(str(file.category), "Photos")
        self.assertEqual(file.get_absolute_url(), f"/?file={file.pk}")
        self.assertEqual(file.download_name, "photo.png")


class StorageTests(TestCase):
    @override_settings(STORAGE_QUOTA_BYTES=1234)
    def test_load_creates_the_single_row_from_settings(self):
        self.assertEqual(Storage.load().quota_bytes, 1234)
        Storage.objects.filter(pk=1).update(quota_bytes=99)
        self.assertEqual(Storage.load().quota_bytes, 99)
        self.assertEqual(Storage.objects.count(), 1)
        self.assertEqual(str(Storage.load()), "File storage")
