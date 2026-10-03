from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from catalog import media
from catalog.models import File


@receiver(post_delete, sender=File)
def delete_stored_files(sender, instance, **kwargs):
    names = [field.name for field in (instance.file, instance.thumbnail) if field]
    transaction.on_commit(lambda: media.delete_files(names))
