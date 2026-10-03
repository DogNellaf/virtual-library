from django.conf import settings

from catalog.views import THEME_COOKIE, THEMES


def ui(request):
    theme = request.COOKIES.get(THEME_COOKIE)
    return {
        "theme": theme if theme in ("light", "dark") else "auto",
        "themes": THEMES,
        "demo_username": settings.DEMO_USERNAME,
        "demo_password": settings.DEMO_PASSWORD,
    }
