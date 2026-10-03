from pathlib import PurePath

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models, transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from catalog import media


def search_key(text: str) -> str:
    """Case- and ё-insensitive form of a string, used for search and sorting."""
    return " ".join(text.casefold().replace("ё", "е").split())


class Category(models.Model):
    name = models.CharField(_("name"), max_length=200, unique=True)
    description = models.TextField(
        _("description"), blank=True, help_text=_("Internal note, not shown in the catalog.")
    )

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")
        ordering = ["name"]

    def __str__(self):
        return self.name


class File(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", _("Image")
        DOCUMENT = "document", _("Document")
        SPREADSHEET = "spreadsheet", _("Spreadsheet")
        PRESENTATION = "presentation", _("Presentation")
        AUDIO = "audio", _("Audio")
        VIDEO = "video", _("Video")
        ARCHIVE = "archive", _("Archive")
        OTHER = "other", _("Other")

    title = models.CharField(_("title"), max_length=200)
    file = models.FileField(_("file"), upload_to="uploads/%Y/%m/", max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="files", verbose_name=_("category")
    )
    description = models.TextField(_("description"), blank=True)
    upload_date = models.DateTimeField(_("uploaded"), auto_now_add=True, db_index=True)

    # Filled from the uploaded file on save, so the catalog never touches the disk.
    original_name = models.CharField(_("original name"), max_length=255, editable=False, default="")
    size = models.PositiveBigIntegerField(_("size, bytes"), default=0, editable=False)
    kind = models.CharField(
        _("type"), max_length=20, choices=Kind, default=Kind.OTHER, editable=False, db_index=True
    )
    width = models.PositiveIntegerField(null=True, editable=False)
    height = models.PositiveIntegerField(null=True, editable=False)
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True, editable=False)
    title_key = models.CharField(max_length=200, editable=False, db_index=True, default="")
    search_text = models.TextField(editable=False, default="")

    class Meta:
        verbose_name = _("file")
        verbose_name_plural = _("files")
        ordering = ["-upload_date", "-id"]
        indexes = [
            # Lets the substring search (LIKE '%...%') use an index instead of a full scan.
            GinIndex(fields=["search_text"], opclasses=["gin_trgm_ops"], name="file_search_trgm"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        stale = []
        if self.file and not self.file._committed:
            if self.pk:
                old = File.objects.filter(pk=self.pk).values_list("file", "thumbnail").first()
                stale = [name for name in old or () if name]
            self.original_name = PurePath(self.file.name).name[:255]
            info = media.inspect(self.file)
            self.size, self.kind = info.size, info.kind
            self.width, self.height = info.width, info.height
            self.thumbnail = None
            if info.thumbnail is not None:
                self.thumbnail.save(f"{PurePath(self.file.name).stem}.webp", info.thumbnail, False)
        self.title_key = search_key(self.title)[:200]
        self.search_text = search_key(f"{self.title} {self.description} {self.original_name}")
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "title_key", "search_text"}
        super().save(*args, **kwargs)
        if stale:
            # Old files are removed only once the new row is committed.
            transaction.on_commit(lambda: media.delete_files(stale))

    def get_absolute_url(self):
        return f"{reverse('index')}?file={self.pk}"

    @property
    def extension(self) -> str:
        return PurePath(self.original_name or self.file.name).suffix.lstrip(".").upper()

    @property
    def is_image(self) -> bool:
        return self.kind == self.Kind.IMAGE

    @property
    def download_name(self) -> str:
        return self.original_name or PurePath(self.file.name).name


class Storage(models.Model):
    """The single row that holds the quota. Uploads lock it, so they are serialized."""

    quota_bytes = models.PositiveBigIntegerField(
        _("quota, bytes"), help_text=_("Total size of all files. 0 means no limit.")
    )

    class Meta:
        verbose_name = _("storage")
        verbose_name_plural = _("storage")

    def __str__(self):
        return str(_("File storage"))

    @classmethod
    def load(cls) -> "Storage":
        storage, _created = cls.objects.get_or_create(
            pk=1, defaults={"quota_bytes": settings.STORAGE_QUOTA_BYTES}
        )
        return storage
