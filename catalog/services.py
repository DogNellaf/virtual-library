"""Operations on the library that have to stay consistent: quota and uploads."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext as _

from catalog.models import Category, File, Storage


class QuotaExceeded(ValidationError):
    pass


@dataclass(frozen=True)
class StorageSummary:
    used: int
    quota: int

    @property
    def percent(self) -> float:
        if not self.quota:
            return 0.0
        return min(100.0, round(self.used * 100 / self.quota, 1))


def used_bytes(exclude: File | None = None) -> int:
    files = File.objects.all()
    if exclude is not None and exclude.pk:
        files = files.exclude(pk=exclude.pk)
    return files.aggregate(total=Coalesce(Sum("size"), 0))["total"]


def storage_summary() -> StorageSummary:
    return StorageSummary(used=used_bytes(), quota=Storage.load().quota_bytes)


def reserve_space(size: int, replacing: File | None = None) -> None:
    """Check that `size` more bytes fit into the quota.

    Must run inside a transaction. The storage row stays locked until it ends, so two
    uploads can never both pass the check against the same free space.
    """
    Storage.load()
    storage = Storage.objects.select_for_update().get(pk=1)
    if not storage.quota_bytes:
        return
    free = storage.quota_bytes - used_bytes(exclude=replacing)
    if size > free:
        raise QuotaExceeded(
            _("Not enough space: the file is %(size)s, %(free)s left of %(quota)s.")
            % {
                "size": filesizeformat(size),
                "free": filesizeformat(max(free, 0)),
                "quota": filesizeformat(storage.quota_bytes),
            },
            code="quota",
        )


def add_file(*, title: str, category: Category, upload, description: str = "") -> File:
    with transaction.atomic():
        reserve_space(upload.size)
        file = File(title=title, category=category, description=description, file=upload)
        file.save()
    return file
