# Dockerfile для Django-приложения
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# системные зависимости для psycopg2 и netcat
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    netcat \
  && rm -rf /var/lib/apt/lists/*

# скопировать requirements (или poetry/pyproject) и установить зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

# копируем проект
COPY . /app

# делаем скрипт стартовый исполняемым
COPY start.sh /start.sh
RUN chmod +x /start.sh

# порт приложения
EXPOSE 8000

# default command — через docker-compose переопределяем на /start.sh
CMD ["/start.sh"]
