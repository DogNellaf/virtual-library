#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py ensure_admin
if [ "$DEMO_SEED" = "True" ]; then
    python manage.py seed_demo
fi

exec "$@"
