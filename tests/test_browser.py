from contextlib import nullcontext
from pathlib import Path
from threading import Event, Timer

import pytest
from playwright.sync_api import sync_playwright

from monitor.core import Group
from monitor.facebook import ScanStopped, SessionRequired, check_stop, login, read_group


@pytest.fixture
def context():
    with sync_playwright() as pw:
        # Local fixtures only. No real Facebook request, credentials, or saved profile.
        browser = pw.chromium.launch(channel="msedge", headless=True, chromium_sandbox=True, timeout=20000)
        context = browser.new_context()
        context.add_cookies(
            [
                {"name": name, "value": "fixture-only", "domain": ".facebook.com", "path": "/"}
                for name in ("c_user", "xs")
            ]
        )
        context.set_default_timeout(5000)
        context.set_default_navigation_timeout(15000)
        yield context
        browser.close()


@pytest.mark.browser
def test_login_dispatches_delayed_requests_while_waiting_for_user(context, monkeypatch, tmp_path):
    stop, confirm, dispatched = Event(), Event(), Event()

    def route_request(route):
        if route.request.url.endswith("/probe"):
            route.fulfill(body="ok")
            dispatched.set()
            stop.set()
        else:
            route.fulfill(
                content_type="text/html",
                body="""<!doctype html>
                <script>setTimeout(() => fetch('/probe'), 150)</script>Login fixture""",
            )

    context.route("**/*", route_request)
    monkeypatch.setattr("monitor.facebook.open_browser", lambda *args: nullcontext(context))
    watchdog = Timer(4, stop.set)
    watchdog.start()
    try:
        with pytest.raises(ScanStopped):
            login(tmp_path, "msedge", stop, confirm, lambda *args: None)
        assert dispatched.is_set(), (
            "Login wait must keep processing browser requests before the user confirms"
        )
    finally:
        watchdog.cancel()


@pytest.mark.browser
def test_feed_scoping_expansion_urls_times_and_limit(context, monkeypatch):
    html = (Path(__file__).parent / "fixtures" / "feed.html").read_text(encoding="utf-8")
    context.route("**/*", lambda route: route.fulfill(body=html, content_type="text/html; charset=utf-8"))
    monkeypatch.setattr("monitor.facebook.pause", lambda stop, seconds: check_stop(stop))
    found = []
    group = Group("IT Jobs", "https://www.facebook.com/groups/123")
    read_group(
        context,
        group,
        ["java intern", "spring boot", "flutter"],
        30,
        Event(),
        lambda *args: None,
        found.append,
    )
    assert len(found) == 3
    assert found[0].keywords == ["java intern", "spring boot"]
    assert found[0].posted_at == "2026-09-07T07:35:00+00:00"
    assert found[1].url.endswith("/posts/789")
    assert found[1].content == "Tuyển thực tập backend biết Spring Boot"
    assert found[1].posted_at is None
    assert found[1].posted_time_raw == "2 giờ"
    assert found[2].url.endswith("/posts/801")
    assert all("flutter" not in post.keywords for post in found)
    found.clear()
    read_group(context, group, ["java intern"], 1, Event(), lambda *args: None, found.append)
    assert len(found) == 1
    assert not context.pages


@pytest.mark.browser
def test_modern_feed_uses_real_cards_and_hovers_timestamp(context, monkeypatch):
    html = (Path(__file__).parent / "fixtures" / "feed_modern.html").read_text(encoding="utf-8")
    context.route("**/*", lambda route: route.fulfill(body=html, content_type="text/html; charset=utf-8"))
    monkeypatch.setattr("monitor.facebook.pause", lambda stop, seconds: check_stop(stop))
    found = []
    read_group(
        context,
        Group("IT Jobs", "https://www.facebook.com/groups/123"),
        ["java intern", "spring boot", "flutter"],
        1,
        Event(),
        lambda *args: None,
        found.append,
    )
    assert len(found) == 1
    assert found[0].url == "https://www.facebook.com/groups/123/posts/900"
    assert found[0].content == "Tuyển JAVA INTERN biết Spring Boot"
    assert found[0].keywords == ["java intern", "spring boot"]
    assert found[0].posted_time_raw == "1 giờ"


@pytest.mark.browser
def test_feed_removal_during_hover_does_not_shift_card_identity(context, monkeypatch):
    html = """<div role="feed">
      <div><a href="?ref=fixture" onmouseenter="document.getElementById('obsolete')?.remove();this.href='/groups/123/posts/101/'">1 hour</a>
        <div data-ad-rendering-role="story_message">Java first post</div></div>
      <div id="obsolete"><a href="/groups/123/posts/102/">2 hours</a>
        <div data-ad-rendering-role="story_message">Java removed post</div></div>
      <div><a href="/groups/123/posts/103/">3 hours</a>
        <div data-ad-rendering-role="story_message">Java last post</div></div>
    </div>"""
    context.route("**/*", lambda route: route.fulfill(body=html, content_type="text/html"))
    monkeypatch.setattr("monitor.facebook.pause", lambda stop, seconds: check_stop(stop))
    found, logs = [], []
    read_group(
        context,
        Group("group", "https://www.facebook.com/groups/123"),
        ["java"],
        30,
        Event(),
        lambda kind, message: logs.append(message),
        found.append,
    )
    assert [(post.url.rsplit("/", 1)[-1], post.content) for post in found] == [
        ("101", "Java first post"),
        ("103", "Java last post"),
    ]
    assert "1 lần thẻ đổi/timeout" in logs[-1]


@pytest.mark.browser
def test_replaced_card_during_expansion_is_picked_up_next_round(context, monkeypatch):
    html = """<div role="feed"><div id="changing">
      <a href="/groups/123/posts/101/">1 hour</a>
      <div data-ad-rendering-role="story_message">Java
        <button onclick="document.getElementById('changing').outerHTML = document.getElementById('replacement').innerHTML">See more</button>
      </div></div></div>
      <template id="replacement"><div><a href="/groups/123/posts/101/">1 hour</a>
        <div data-ad-rendering-role="story_message">Java expanded replacement</div></div></template>"""
    context.route("**/*", lambda route: route.fulfill(body=html, content_type="text/html"))
    monkeypatch.setattr("monitor.facebook.pause", lambda stop, seconds: check_stop(stop))
    found = []
    read_group(
        context,
        Group("group", "https://www.facebook.com/groups/123"),
        ["java"],
        30,
        Event(),
        lambda *args: None,
        found.append,
    )
    assert len(found) == 1
    assert found[0].content == "Java expanded replacement"


@pytest.mark.browser
def test_unreadable_feed_is_an_error_and_stop_closes_page(context, monkeypatch):
    context.route(
        "**/*",
        lambda route: route.fulfill(
            body="<html><body>Group unavailable</body></html>", content_type="text/html"
        ),
    )
    monkeypatch.setattr("monitor.facebook.pause", lambda stop, seconds: check_stop(stop))
    group = Group("IT Jobs", "https://www.facebook.com/groups/123")
    with pytest.raises(RuntimeError, match="Không đọc được"):
        read_group(context, group, ["java"], 30, Event(), lambda *args: None, lambda *args: None)
    stop = Event()
    stop.set()
    with pytest.raises(ScanStopped):
        read_group(context, group, ["java"], 30, stop, lambda *args: None, lambda *args: None)
    assert not context.pages


@pytest.mark.browser
def test_login_wall_never_reported_as_empty_success(context, monkeypatch):
    context.route(
        "**/*",
        lambda route: route.fulfill(body='<input name="email"><input name="pass">', content_type="text/html"),
    )
    monkeypatch.setattr("monitor.facebook.pause", lambda stop, seconds: check_stop(stop))
    with pytest.raises(SessionRequired):
        read_group(
            context,
            Group("IT Jobs", "https://www.facebook.com/groups/123"),
            ["java"],
            30,
            Event(),
            lambda *args: None,
            lambda *args: None,
        )
