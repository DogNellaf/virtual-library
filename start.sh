#!/bin/bash

# Применение миграций
python manage.py migrate

python manage.py create_update_admin

# Сбор статических файлов
python manage.py collectstatic --noinput

# Запуск Gunicorn
echo "-> Starting gunicorn"
exec gunicorn virtual_library.wsgi:application --bind 0.0.0.0:8000