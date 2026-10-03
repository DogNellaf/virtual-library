import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from catalog.models import Category, File


def png_bytes(size=(120, 80), color=(30, 120, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def upload(name="photo.png", content=None) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, png_bytes() if content is None else content)


def make_category(name="Photos") -> Category:
    return Category.objects.get_or_create(name=name)[0]


def make_file(category=None, title="Sunset", name="photo.png", content=None, **fields) -> File:
    file = File(
        title=title,
        category=category or make_category(),
        file=upload(name, content),
        **fields,
    )
    file.save()
    return file


class TempMediaMixin:
    """Every test class writes uploads into its own temporary directory."""

    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix="library-test-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
