import os
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.core.management.base import BaseCommand

User = get_user_model()

class Command(BaseCommand):
    help = 'Create or update admin user'

    def handle(self, *args, **options):
        admin_username = os.environ.get('ADMIN_USERNAME')
        admin_password = os.environ.get('ADMIN_PASSWORD')

        if not admin_username or not admin_password:
            self.stderr.write('Error: ADMIN_USERNAME and ADMIN_PASSWORD must be set in environment')
            return

        try:
            user = User.objects.get(username=admin_username)
            
            # Проверяем пароль
            if not check_password(admin_password, user.password):
                user.password = make_password(admin_password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Password updated for user "{admin_username}"')
                )
            else:
                self.stdout.write(f'User "{admin_username}" already exists with correct password')

        except User.DoesNotExist:
            # Создаем нового пользователя
            User.objects.create_user(
                username=admin_username,
                password=admin_password,
                is_staff=True,
                is_superuser=True
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created superuser "{admin_username}"')
            )
