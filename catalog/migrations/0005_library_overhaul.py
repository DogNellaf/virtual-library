from pathlib import PurePath

import django.db.models.deletion
from django.db import migrations, models

from catalog import media
from catalog.models import search_key


def make_category_names_unique(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    seen = set()
    for category in Category.objects.order_by("id"):
        name, n = category.name, 2
        while name in seen:
            name, n = f"{category.name} ({n})", n + 1
        if name != category.name:
            category.name = name
            category.save(update_fields=["name"])
        seen.add(name)


def fill_file_metadata(apps, schema_editor):
    """Existing rows get the size, type, thumbnail and search keys new uploads get on save."""
    File = apps.get_model("catalog", "File")
    for file in File.objects.all():
        file.original_name = PurePath(file.file.name).name[:255]
        file.kind = media.kind_for_extension(file.file.name)
        try:
            with file.file.open("rb"):
                info = media.inspect(file.file)
                file.size, file.kind = info.size, info.kind
                file.width, file.height = info.width, info.height
                if info.thumbnail is not None:
                    name = f"{PurePath(file.file.name).stem}.webp"
                    file.thumbnail.save(name, info.thumbnail, save=False)
        except FileNotFoundError:
            pass
        file.title_key = search_key(file.title)[:200]
        file.search_text = search_key(f"{file.title} {file.description} {file.original_name}")
        file.save()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_alter_file_file"),
    ]

    operations = [
        migrations.CreateModel(
            name="Storage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "quota_bytes",
                    models.PositiveBigIntegerField(
                        help_text="Total size of all files. 0 means no limit.",
                        verbose_name="quota, bytes",
                    ),
                ),
            ],
            options={
                "verbose_name": "storage",
                "verbose_name_plural": "storage",
            },
        ),
        migrations.AlterModelOptions(
            name="category",
            options={
                "ordering": ["name"],
                "verbose_name": "category",
                "verbose_name_plural": "categories",
            },
        ),
        migrations.AlterModelOptions(
            name="file",
            options={
                "ordering": ["-upload_date", "-id"],
                "verbose_name": "file",
                "verbose_name_plural": "files",
            },
        ),
        migrations.AddField(
            model_name="file",
            name="height",
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="file",
            name="kind",
            field=models.CharField(
                choices=[
                    ("image", "Image"),
                    ("document", "Document"),
                    ("spreadsheet", "Spreadsheet"),
                    ("presentation", "Presentation"),
                    ("audio", "Audio"),
                    ("video", "Video"),
                    ("archive", "Archive"),
                    ("other", "Other"),
                ],
                db_index=True,
                default="other",
                editable=False,
                max_length=20,
                verbose_name="type",
            ),
        ),
        migrations.AddField(
            model_name="file",
            name="original_name",
            field=models.CharField(
                default="", editable=False, max_length=255, verbose_name="original name"
            ),
        ),
        migrations.AddField(
            model_name="file",
            name="search_text",
            field=models.TextField(default="", editable=False),
        ),
        migrations.AddField(
            model_name="file",
            name="size",
            field=models.PositiveBigIntegerField(
                default=0, editable=False, verbose_name="size, bytes"
            ),
        ),
        migrations.AddField(
            model_name="file",
            name="thumbnail",
            field=models.ImageField(blank=True, editable=False, upload_to="thumbnails/"),
        ),
        migrations.AddField(
            model_name="file",
            name="title_key",
            field=models.CharField(db_index=True, default="", editable=False, max_length=200),
        ),
        migrations.AddField(
            model_name="file",
            name="width",
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="category",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Internal note, not shown in the catalog.",
                verbose_name="description",
            ),
        ),
        migrations.RunPython(make_category_names_unique, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="category",
            name="name",
            field=models.CharField(max_length=200, unique=True, verbose_name="name"),
        ),
        migrations.AlterField(
            model_name="file",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="files",
                to="catalog.category",
                verbose_name="category",
            ),
        ),
        migrations.AlterField(
            model_name="file",
            name="description",
            field=models.TextField(blank=True, verbose_name="description"),
        ),
        migrations.AlterField(
            model_name="file",
            name="file",
            field=models.FileField(max_length=255, upload_to="uploads/%Y/%m/", verbose_name="file"),
        ),
        migrations.AlterField(
            model_name="file",
            name="title",
            field=models.CharField(max_length=200, verbose_name="title"),
        ),
        migrations.AlterField(
            model_name="file",
            name="upload_date",
            field=models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="uploaded"),
        ),
        migrations.RunPython(fill_file_metadata, migrations.RunPython.noop),
    ]
