"""Feed reading adapted from demo/bot-condo/scraper/{browser,feed}.py.

Only browser/session and feed concepts are reused; no AI, rental rules or comments.
Selectors are deliberately conservative: unreadable cards are reported, not invented.
"""

import hashlib
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Event
from urllib.parse import urlparse

from playwright.sync_api import Error as BrowserError
from playwright.sync_api import TimeoutError as BrowserTimeout
from playwright.sync_api import sync_playwright

from monitor.core import Group, Post, group_url, match_keywords, post_url


class ScanStopped(Exception):
    pass


class SessionRequired(RuntimeError):
    pass


class CardChanged(RuntimeError):
    """A feed card was removed while we were inspecting it."""


def require_card(card):
    if not card.evaluate("node => node.isConnected"):
        raise CardChanged()


def expand_card(card):
    for message in card.query_selector_all(MESSAGE_SELECTOR):
        if not card.evaluate(OWN_NODE, message):
            continue
        for button in message.query_selector_all('[role="button"], button, a'):
            if re.fullmatch(r"Xem thêm|See more", button.inner_text().strip(), re.I):
                if button.is_visible():
                    button.click(timeout=3000)
                    require_card(card)
                    return


def check_stop(stop: Event):
    if stop.is_set():
        raise ScanStopped()


def pause(stop: Event, seconds: float):
    if stop.wait(seconds):
        raise ScanStopped()


@contextmanager
def open_browser(data_dir, channel):
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(data_dir / "browser-profiles" / channel),
            channel=channel,
            headless=False,
            chromium_sandbox=True,
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            viewport={"width": 1280, "height": 900},
            timeout=20000,
        )
        context.set_default_timeout(5000)
        context.set_default_navigation_timeout(15000)
        try:
            yield context
        finally:
            context.close()


def session_valid(context, page):
    parsed = urlparse(page.url)
    if parsed.hostname not in {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com"}:
        return False
    path = parsed.path.casefold()
    if any(word in path for word in ("login", "checkpoint", "two_step", "recover", "challenge")):
        return False
    cookies = {cookie["name"] for cookie in context.cookies("https://www.facebook.com/")}
    login_inputs = page.locator('input[name="email"], input[name="pass"]')
    return {"c_user", "xs"}.issubset(cookies) and not any(
        login_inputs.nth(i).is_visible() for i in range(login_inputs.count())
    )


def require_session(context, page):
    if not session_valid(context, page):
        raise SessionRequired("Facebook cần đăng nhập hoặc xác minh. Đã dừng lịch quét; hãy đăng nhập lại.")


def login(data_dir, channel, stop, confirm, emit):
    with open_browser(data_dir, channel) as context:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        emit("login_ready", "Đăng nhập trực tiếp trong trình duyệt, sau đó bấm ‘Đã đăng nhập’.")
        while True:
            check_stop(stop)
            if page.is_closed():
                raise ScanStopped()
            # Pump Playwright's sync dispatcher while waiting for a human. Event.wait()
            # blocks it indefinitely and leaves navigation/network events unprocessed.
            page.wait_for_timeout(250)
            check_stop(stop)
            if page.is_closed():
                raise ScanStopped()
            if confirm.is_set():
                confirm.clear()
                if session_valid(context, page):
                    emit("log", "Đã xác nhận phiên Facebook. Profile được lưu khi đóng trình duyệt.")
                    return
                emit("login_ready", "Chưa xác nhận được đăng nhập. Hoàn tất đăng nhập/xác minh rồi bấm lại.")


MESSAGE_SELECTOR = (
    '[data-ad-preview="message"], [data-ad-comet-preview="message"], [data-ad-rendering-role="story_message"]'
)

OWN_NODE = """(card, node) => {
    const firstMessage = card.querySelector('[data-ad-preview="message"], [data-ad-comet-preview="message"], [data-ad-rendering-role="story_message"]');
    const primary = card.matches('[role="article"]') ? card : firstMessage?.closest('[role="article"]');
    const article = node.closest('[role="article"]');
    return !article || article === primary || !card.contains(article);
}"""

CARD_DATA = r"""el => {
    const firstMessage = el.querySelector('[data-ad-preview="message"], [data-ad-comet-preview="message"], [data-ad-rendering-role="story_message"]');
    const primary = el.matches('[role="article"]') ? el : firstMessage?.closest('[role="article"]');
    const own = node => {
        const article = node.closest('[role="article"]');
        return !article || article === primary || !el.contains(article);
    };
    const selectors = ['[data-ad-preview="message"]', '[data-ad-comet-preview="message"]',
                       '[data-ad-rendering-role="story_message"]'];
    let messages = [];
    for (const selector of selectors) {
        messages = [...el.querySelectorAll(selector)].filter(own);
        if (messages.length) break;
    }
    const text = messages.map(node => node.innerText.trim()).filter(Boolean).join('\n');
    const links = [...el.querySelectorAll('a[href]')]
        .filter(node => own(node) && !messages.some(message => message.contains(node)))
        .map(node => {
            const time = node.querySelector('time,abbr');
            return {href: node.href,
                    raw: node.getAttribute('aria-label') || time?.getAttribute('title') || node.innerText,
                    datetime: time?.getAttribute('datetime') || '',
                    utime: time?.getAttribute('data-utime') || ''};
        });
    return {text, links};
}"""


def read_card(card, page, source, stop):
    """Facebook may only populate the timestamp permalink after mouse hover."""
    data = card.evaluate(CARD_DATA)
    if any(post_url(link["href"], source) for link in data["links"]):
        return data
    anchors = card.query_selector_all("a[href]")
    hovered = 0
    for anchor in anchors[:30]:
        check_stop(stop)
        require_card(card)
        if not anchor.evaluate("node => node.isConnected"):
            continue
        if not card.evaluate(OWN_NODE, anchor):
            continue
        if anchor.evaluate("n => !!n.closest('" + MESSAGE_SELECTOR.replace("'", "\\'") + "')"):
            continue
        # Resolve query-only hrefs against the current group page, not facebook.com/.
        href = anchor.evaluate("node => node.href") or ""
        try:
            is_placeholder = href == "#" or group_url(href) == group_url(source)
        except ValueError:
            is_placeholder = False
        if not is_placeholder or not anchor.is_visible():
            continue
        anchor.hover(timeout=3000)
        page.wait_for_timeout(350)
        require_card(card)
        hovered += 1
        data = card.evaluate(CARD_DATA)
        if any(post_url(link["href"], source) for link in data["links"]):
            break
        if hovered >= 3:
            break
    return data


def parse_posted_time(link):
    try:
        if link.get("utime"):
            return datetime.fromtimestamp(int(link["utime"]), timezone.utc).isoformat()
        if link.get("datetime"):
            value = datetime.fromisoformat(link["datetime"].replace("Z", "+00:00"))
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    return None


def read_group(context, group: Group, keywords, max_posts, stop, emit, on_post):
    page = context.new_page()
    visited, unreadable = set(), set()
    missing_text, missing_link = set(), set()
    max_cards, transient_cards = 0, 0
    delivered, matched = 0, 0
    try:
        check_stop(stop)
        page.goto(group.url + "?sorting_setting=CHRONOLOGICAL", wait_until="domcontentloaded")
        pause(stop, 3)
        require_session(context, page)
        # Finite scan budget even when Facebook repeats cards or gives no usable IDs.
        for _ in range(10):
            check_stop(stop)
            require_session(context, page)
            selector = '[role="feed"] > div'
            cards = page.locator(selector).filter(has=page.locator(MESSAGE_SELECTOR))
            if not cards.count():
                selector = '[role="article"]'
                cards = page.locator(selector)
                if not cards.count():
                    selector = 'div[data-pagelet*="FeedUnit"]'
                    cards = page.locator(selector)
            # Freeze DOM identities, not nth() positions. Facebook virtualizes/reorders
            # cards during scroll, expansion and hover. A detached handle is skipped;
            # fresh replacements are picked up in the next bounded scroll round.
            snapshot = cards.element_handles()[:150]
            max_cards = max(max_cards, len(snapshot))
            for card in snapshot:
                check_stop(stop)
                try:
                    require_card(card)
                    if card.evaluate("(el, selector) => !!el.parentElement.closest(selector)", selector):
                        continue
                    expand_card(card)
                    data = read_card(card, page, group.url, stop)
                    require_card(card)
                except (CardChanged, BrowserTimeout):
                    if page.is_closed():
                        raise
                    transient_cards += 1
                    continue
                except BrowserError:
                    # Ignore only a detached card, not browser/network/session failures.
                    if page.is_closed() or card.evaluate("node => node.isConnected"):
                        raise
                    transient_cards += 1
                    continue
                identity, time_data = None, {}
                for link in data["links"]:
                    candidate = post_url(link["href"], group.url)
                    if candidate:
                        identity, time_data = candidate, link
                        break
                text = data["text"].strip()
                if not identity or not text:
                    # No whole-card text fallback: that could match a comment/author/UI label.
                    fingerprint = hashlib.sha256((identity or str(data)).encode()).hexdigest()
                    unreadable.add(fingerprint)
                    if not text:
                        missing_text.add(fingerprint)
                    if not identity:
                        missing_link.add(fingerprint)
                    if len(visited) + len(unreadable) >= max_posts:
                        break
                    continue
                if identity in visited:
                    continue
                visited.add(identity)
                hits = match_keywords(text, keywords)
                if hits:
                    on_post(
                        Post(
                            identity,
                            group.name,
                            group.url,
                            text,
                            hits,
                            posted_at=parse_posted_time(time_data),
                            posted_time_raw=(time_data.get("raw") or "").strip(),
                        )
                    )
                    matched += 1
                delivered += 1
                if len(visited) + len(unreadable) >= max_posts:
                    break
            if len(visited) + len(unreadable) >= max_posts:
                break
            page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
            pause(stop, 2)
        require_session(context, page)
        if not delivered:
            raise RuntimeError(
                f"Không đọc được bài hợp lệ: tìm thấy tối đa {max_cards} thẻ, "
                f"{len(missing_text)} thẻ thiếu nội dung, {len(missing_link)} thẻ thiếu permalink. Group có thể trống, "
                f"{transient_cards} lần thẻ đổi/timeout; "
                "chưa có quyền truy cập hoặc giao diện Facebook đã thay đổi."
            )
        emit(
            "log",
            f"{group.name}: đọc {delivered} bài, {matched} khớp; "
            f"bỏ qua {len(unreadable)} thẻ không đủ nội dung/link, {transient_cards} lần thẻ đổi/timeout.",
        )
    finally:
        page.close()
