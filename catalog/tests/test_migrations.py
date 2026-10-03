import shutil
import tempfile
from pathlib import Path

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from catalog.tests.factories import png_bytes


class LibraryOverhaulMigrationTests(TransactionTestCase):
    """Rows from the original prototype get metadata, thumbnails and unique category names."""

    before = [("catalog", "0004_alter_file_file")]
    after = [("catalog", "0005_library_overhaul")]

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        executor.loader.build_graph()
        return executor.loader.project_state(target).apps

    def test_existing_rows_are_upgraded(self):
        apps = self.migrate(self.before)
        Category = apps.get_model("catalog", "Category")
        File = apps.get_model("catalog", "File")
        first = Category.objects.create(name="Photos")
        Category.objects.create(name="Photos")
        uploads = Path(self.media, "uploads")
        uploads.mkdir()
        (uploads / "1.png").write_bytes(png_bytes((300, 200)))
        File.objects.create(title="Ёлка", file="uploads/1.png", category=first)
        File.objects.create(title="Lost", file="uploads/missing.pdf", category=first)

        apps = self.migrate(self.after)
        Category = apps.get_model("catalog", "Category")
        File = apps.get_model("catalog", "File")
        self.assertEqual(
            sorted(Category.objects.values_list("name", flat=True)), ["Photos", "Photos (2)"]
        )
        image = File.objects.get(title="Ёлка")
        self.assertEqual(
            (image.kind, image.width, image.size), ("image", 300, len(png_bytes((300, 200))))
        )
        self.assertTrue(Path(self.media, image.thumbnail.name).exists())
        self.assertEqual(image.title_key, "елка")
        lost = File.objects.get(title="Lost")
        self.assertEqual((lost.kind, lost.size, lost.original_name), ("document", 0, "missing.pdf"))
