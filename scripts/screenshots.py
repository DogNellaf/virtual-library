"""Take the README screenshots from a running stack, in every language.

    docker compose up --build --detach --wait
    python scripts/screenshots.py

The demo content is recreated first, so the pictures never show test uploads.
"""

import os
import subprocess
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}
LANGUAGES = ["en", "ru", "fr", "de"]


def reseed() -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "seed_demo", "--reset"],
        check=True,
    )


def open_page(page: Page, path: str) -> None:
    page.goto(BASE_URL + path)
    page.evaluate(
        "document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')"
    )
    page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth > 0)")


def file_id(page: Page, title: str) -> str:
    page.goto(f"{BASE_URL}/?q={title}")
    href = page.locator(".files .card").first.get_attribute("href")
    return href.rsplit("file=", 1)[1]


def shoot(browser, language: str) -> None:
    out = OUT / language
    out.mkdir(parents=True, exist_ok=True)
    cookies = [{"name": "django_language", "value": language, "url": BASE_URL}]

    def context(theme="light", viewport=DESKTOP, **kwargs):
        # The page CSP forbids eval, which Playwright needs to wait for images.
        ctx = browser.new_context(
            viewport=viewport, device_scale_factor=1, bypass_csp=True, **kwargs
        )
        ctx.add_cookies([*cookies, {"name": "theme", "value": theme, "url": BASE_URL}])
        return ctx

    desktop = context().new_page()
    valley = file_id(desktop, "valley")
    report = file_id(desktop, "annual")
    poster = file_id(desktop, "bauhaus")

    open_page(desktop, "/")
    desktop.screenshot(path=out / "catalog.png")
    open_page(desktop, f"/?file={valley}")
    desktop.screenshot(path=out / "details.png")
    open_page(desktop, f"/?file={poster}#zoom")
    desktop.screenshot(path=out / "zoom.png")
    category = desktop.locator(".sidebar .nav-item").nth(2).get_attribute("href")
    open_page(desktop, f"{category}&view=list&file={report}")
    desktop.screenshot(path=out / "list.png")
    open_page(desktop, "/?q=no+such+file")
    desktop.screenshot(path=out / "empty-search.png")

    admin = context().new_page()
    admin.goto(BASE_URL + "/admin/login/")
    admin.screenshot(path=out / "admin-login.png")
    admin.fill("#id_username", "demo")
    admin.fill("#id_password", "demo12345")
    admin.click("[type=submit]")
    open_page(admin, "/admin/catalog/file/")
    admin.screenshot(path=out / "admin-files.png")

    dark = context(theme="dark").new_page()
    open_page(dark, f"/?file={valley}")
    dark.screenshot(path=out / "dark.png")

    phone = context(viewport=PHONE, is_mobile=True, has_touch=True).new_page()
    open_page(phone, "/")
    phone.screenshot(path=out / "mobile.png")
    open_page(phone, f"/?file={valley}")
    phone.screenshot(path=out / "mobile-details.png")


def main() -> None:
    reseed()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))
        for language in LANGUAGES:
            shoot(browser, language)
        browser.close()
    pngs = sorted(str(p) for p in OUT.glob("*/*.png"))
    subprocess.run(
        ["pngquant", "--quality=80-95", "--speed=1", "--strip", "--force", "--ext=.png", *pngs],
        check=True,
    )
    print(f"Saved {len(pngs)} screenshots to {OUT}")


if __name__ == "__main__":
    main()
