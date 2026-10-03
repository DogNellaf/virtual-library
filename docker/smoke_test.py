"""Browser smoke test of a running stack.

    BASE_URL=http://localhost:8000 python docker/smoke_test.py

Walks through the catalog and the admin like a visitor and a librarian would, and fails
on any browser console error, including Content Security Policy violations.
"""

import io
import os
import re
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
USERNAME = os.environ.get("DEMO_USERNAME", "demo")
PASSWORD = os.environ.get("DEMO_PASSWORD", "demo12345")
CHROMIUM = os.environ.get("CHROMIUM_PATH")


def step(name: str) -> None:
    print(f"- {name}", flush=True)


def check_health() -> None:
    step("health check")
    with urllib.request.urlopen(f"{BASE_URL}/health/", timeout=10) as response:
        assert response.status == 200, response.status


def browse_catalog(page: Page) -> None:
    step("catalog opens with demo files")
    page.goto(BASE_URL + "/")
    expect(page.get_by_role("heading", name="All files")).to_be_visible()
    expect(page.locator(".files .card")).to_have_count(24)
    expect(page.locator(".pagination")).to_contain_text("Page 1 of 2")

    step("search and details panel")
    page.get_by_role("searchbox").fill("VALLEY")
    page.keyboard.press("Enter")
    expect(page.locator(".files .card")).to_have_count(1)
    page.locator(".files .card").first.click()
    panel = page.locator(".details")
    expect(panel.get_by_role("heading", name="Morning in the valley")).to_be_visible()
    expect(panel).to_contain_text("1600 × 1100 px")
    assert "q=VALLEY" in page.url and "file=" in page.url, page.url

    step("full-size preview")
    panel.locator("a.preview").click()
    lightbox = page.locator(".lightbox")
    expect(lightbox).to_be_visible()
    expect(lightbox.locator("img")).to_have_js_property("complete", True)
    assert lightbox.locator("img").evaluate("img => img.naturalWidth") == 1600
    page.keyboard.press("Escape")
    expect(lightbox).to_be_hidden()

    step("download keeps the original name")
    with page.expect_download() as download_info:
        panel.get_by_role("link", name="Download").click()
    download = download_info.value
    assert download.suggested_filename == "landscape-01.jpg", download.suggested_filename
    assert Path(download.path()).stat().st_size > 10_000

    step("Escape closes the panel, state stays in the URL")
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    assert "q=VALLEY" in page.url and "file=" not in page.url, page.url

    step("category, list view and sorting")
    page.goto(BASE_URL + "/")
    page.locator(".sidebar").get_by_role("link", name="Posters").click()
    page.get_by_role("link", name="List").click()
    page.locator("details.menu summary").first.click()
    page.get_by_role("link", name="Name, A to Z").click()
    expect(page.locator(".files.list .card-title").first).to_have_text("Bauhaus week")
    assert re.search(r"category=\d+.*view=list.*sort=name", page.url), page.url
    page.go_back()
    expect(page.locator(".files.list")).to_be_visible()

    step("file type filter")
    page.goto(BASE_URL + "/")
    page.locator(".chips").get_by_role("link", name=re.compile("Audio")).click()
    expect(page.locator(".files .card")).to_have_count(1)


def switch_language_and_theme(page: Page) -> None:
    step("Russian interface")
    page.goto(BASE_URL + "/")
    page.locator("details.menu summary").nth(1).click()
    page.get_by_role("button", name="Русский").click()
    expect(page.get_by_role("heading", name="Все файлы")).to_be_visible()
    expect(page.locator("html")).to_have_attribute("lang", "ru")

    step("dark theme")
    page.locator("details.menu summary").nth(1).click()
    page.get_by_role("button", name="Тёмная").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    background = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert background == "rgb(17, 19, 23)", background

    page.locator("details.menu summary").nth(1).click()
    page.get_by_role("button", name="English").click()
    expect(page.get_by_role("heading", name="All files")).to_be_visible()


def upload_in_admin(page: Page, tmp: Path) -> None:
    step("admin sign-in with the demo account")
    page.goto(BASE_URL + "/")
    page.get_by_role("link", name="Manage").click()
    expect(page.locator(".demo-credentials")).to_contain_text(USERNAME)
    page.get_by_label("Username").fill(USERNAME)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Log in").click()
    expect(page.get_by_role("link", name="Files")).to_be_visible()

    step("upload a file")
    title = f"Smoke test {uuid.uuid4().hex[:8]}"
    image = tmp / "smoke-test.png"
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), (200, 80, 40)).save(buffer, "PNG")
    image.write_bytes(buffer.getvalue())
    page.goto(BASE_URL + "/admin/catalog/file/add/")
    page.locator("#id_title").fill(title)
    page.locator("#id_category").select_option(label="Posters")
    page.locator("#id_file").set_input_files(image)
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.locator(".messagelist")).to_contain_text("was added successfully")

    step("the upload appears in the catalog")
    page.goto(f"{BASE_URL}/?q={title}")
    expect(page.locator(".files .card")).to_have_count(1)
    page.locator(".files .card").first.click()
    expect(page.locator(".details")).to_contain_text("800 × 600 px")

    step("delete it again")
    page.locator(".details").get_by_role("link", name="Edit").click()
    page.locator("a.deletelink").click()
    page.get_by_role("button", name="Yes, I’m sure").click()
    page.goto(f"{BASE_URL}/?q={title}")
    expect(page.get_by_text("Nothing matches these filters.")).to_be_visible()


def main() -> int:
    check_health()
    errors: list[str] = []
    with sync_playwright() as playwright, tempfile.TemporaryDirectory() as tmp:
        browser = playwright.chromium.launch(executable_path=CHROMIUM)
        context = browser.new_context(accept_downloads=True, locale="en-US")
        page = context.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on(
            "response",
            lambda r: r.status >= 400 and errors.append(f"{r.status} {r.request.method} {r.url}"),
        )
        browse_catalog(page)
        switch_language_and_theme(page)
        upload_in_admin(page, Path(tmp))
        browser.close()
    if errors:
        print("Browser console errors:", *errors, sep="\n  ")
        return 1
    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
