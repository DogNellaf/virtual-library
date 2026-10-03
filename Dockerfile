FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Every dependency ships as a wheel, so the image needs no compiler or libpq headers.
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 1000 app && mkdir -p /app/media && chown -R app:app /app
COPY --chown=app:app . .

USER app
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput -v0
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/', timeout=4)"]

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "virtual_library.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
