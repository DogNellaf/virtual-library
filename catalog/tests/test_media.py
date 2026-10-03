import io
import os
import subprocess
import sys
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from catalog import media
from catalog.tests.factories import png_bytes


class MediaTests(SimpleTestCase):
    def test_palette_image_with_transparency_keeps_alpha(self):
        image = Image.new("P", (40, 40))
        image.info["transparency"] = 0
        buffer = io.BytesIO()
        image.save(buffer, "GIF", transparency=0)
        info = media.inspect(SimpleUploadedFile("a.gif", buffer.getvalue()))
        self.assertEqual(info.kind, "image")
        self.assertEqual(Image.open(info.thumbnail).mode, "RGBA")

    def test_formats_a_browser_cannot_show_are_not_images(self):
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buffer, "TIFF")
        info = media.inspect(SimpleUploadedFile("scan.tiff", buffer.getvalue()))
        self.assertEqual((info.kind, info.thumbnail), ("other", None))

    def test_decompression_bombs_are_not_opened(self):
        with mock.patch.object(Image, "MAX_IMAGE_PIXELS", 10):
            info = media.inspect(SimpleUploadedFile("bomb.png", png_bytes((100, 100))))
        self.assertEqual(info.kind, "other")

    def test_delete_files_survives_storage_errors(self):
        failing = mock.patch.object(media.default_storage, "delete", side_effect=OSError("busy"))
        with failing, self.assertLogs("catalog.media", "WARNING"):
            media.delete_files(["uploads/a.png"])


class SettingsTests(SimpleTestCase):
    def test_production_refuses_to_start_without_a_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != "DJANGO_SECRET_KEY"}
        env.update(DJANGO_DEBUG="False", DJANGO_SETTINGS_MODULE="virtual_library.settings")
        result = subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set DJANGO_SECRET_KEY", result.stderr)
