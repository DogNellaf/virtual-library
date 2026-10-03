import django.contrib.postgres.indexes
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0005_library_overhaul"),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddIndex(
            model_name="file",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_text"],
                name="file_search_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
