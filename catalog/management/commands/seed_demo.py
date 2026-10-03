from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog import demo, services
from catalog.models import Category, File


class Command(BaseCommand):
    help = "Create the demo account and fill an empty library with generated sample files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete all files and categories first."
        )

    def handle(self, *args, reset=False, **options):
        self._ensure_demo_user()
        if reset:
            with transaction.atomic():
                File.objects.all().delete()
                Category.objects.all().delete()
        if File.objects.exists():
            self.stdout.write("The library already has files, nothing to seed.")
            return

        categories = {
            name: Category.objects.get_or_create(name=name, defaults={"description": note})[0]
            for name, note in demo.CATEGORIES.items()
        }
        # Added in reverse, so the newest-first catalog opens with the pictures.
        for seed, item in reversed(list(enumerate(demo.demo_files()))):
            services.add_file(
                title=item.title,
                category=categories[item.category],
                description=item.description,
                upload=demo.build(item, seed),
            )
        self.stdout.write(self.style.SUCCESS(f"Added {File.objects.count()} demo files."))

    def _ensure_demo_user(self):
        username, password = settings.DEMO_USERNAME, settings.DEMO_PASSWORD
        if not username or not password:
            return
        user, created = get_user_model().objects.get_or_create(
            username=username, defaults={"is_staff": True}
        )
        if created:
            user.set_password(password)
            user.save()
            user.user_permissions.set(
                Permission.objects.filter(
                    content_type__app_label="catalog",
                    codename__in=[
                        f"{action}_{model}"
                        for action in ("add", "change", "delete", "view")
                        for model in ("category", "file")
                    ]
                    + ["view_storage"],
                )
            )
            self.stdout.write(self.style.SUCCESS(f'Created demo user "{username}".'))
