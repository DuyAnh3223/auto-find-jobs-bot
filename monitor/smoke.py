"""Offline runtime verification, also exercised from the packaged executable."""

from pathlib import Path

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

from monitor.core import Post
from monitor.exporter import export_posts
from monitor.facebook import CARD_DATA
from monitor.storage import Store


def verify_runtime(data_dir: Path):
    # Dedicated database: never add synthetic rows to the user's results.
    store = Store(data_dir / "smoke.db")
    post = Post(
        "https://www.facebook.com/groups/123/posts/456",
        "Local fixture",
        "https://www.facebook.com/groups/123",
        "JAVA INTERN · Spring Boot",
        ["java intern"],
    )
    store.save_post(post)
    target = data_dir / "smoke.xlsx"
    export_posts(store.posts(), target)
    book = load_workbook(target)
    if book.active["I2"].value != post.content:
        raise RuntimeError("Excel smoke test failed")
    book.close()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True, chromium_sandbox=True, timeout=20000)
        try:
            page = browser.new_page()
            page.set_content('<div role="article"><div data-ad-preview="message">JAVA INTERN</div></div>')
            if page.locator('[role="article"]').evaluate(CARD_DATA)["text"] != "JAVA INTERN":
                raise RuntimeError("Browser smoke test failed")
        finally:
            browser.close()
