#!/bin/sh
set -e

: "${DJANGO_SETTINGS_MODULE:=myproject.settings}"
: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=${POSTGRES_USER}}"
: "${DB_NAME:=${POSTGRES_DB}}"

echo "-> Waiting for database at ${DB_HOST}:${DB_PORT}..."

# wait-for-db (использует netcat)
while ! nc -z ${DB_HOST} ${DB_PORT}; do
  echo "   Waiting for Postgres..."
  sleep 1
done

echo "-> Database is up — running migrations"

# Убедимся, что pip/venv установлен (в контейнере), затем выполняем миграции и collectstatic
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Можно здесь создать суперпользователя автоматически (небезопасно для prod)
# python manage.py createsuperuser --noinput --username admin --email admin@example.com || true

echo "-> Starting gunicorn"
exec gunicorn myproject.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --log-level info
