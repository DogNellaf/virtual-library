import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create the superuser from ADMIN_USERNAME and ADMIN_PASSWORD if it does not exist. "
        "An existing password is kept, so a password changed in the admin survives restarts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Set the password from ADMIN_PASSWORD even if the user exists.",
        )

    def handle(self, *args, reset_password=False, **options):
        username = os.environ.get("ADMIN_USERNAME", "")
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not username or not password:
            self.stdout.write("ADMIN_USERNAME or ADMIN_PASSWORD is not set, skipping.")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username, defaults={"is_staff": True, "is_superuser": True}
        )
        if created or reset_password:
            user.set_password(password)
            user.save()
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created superuser "{username}".'))
        elif reset_password:
            self.stdout.write(self.style.SUCCESS(f'Password reset for "{username}".'))
        else:
            self.stdout.write(f'User "{username}" exists, password kept.')
