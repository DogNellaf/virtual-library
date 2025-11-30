#!/bin/bash

# Ожидание доступности базы данных
echo "-> Waiting for database at db:5432..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "-> Database is up — running migrations"

# Применение миграций
python manage.py migrate

python manage.py create_update_admin

# Сбор статических файлов
python manage.py collectstatic --noinput

# Создание суперпользователя, если не существует
echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='$ADMIN_USERNAME').exists() or User.objects.create_superuser('$ADMIN_USERNAME', '', '$ADMIN_PASSWORD')" | python manage.py shell

# Запуск Gunicorn
echo "-> Starting gunicorn"
exec gunicorn virtual_library.wsgi:application --bind 0.0.0.0:8000