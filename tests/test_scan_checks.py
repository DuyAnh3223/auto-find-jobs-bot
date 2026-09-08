from contextlib import nullcontext

import pytest

from monitor.core import Group, Settings
from monitor.facebook import SessionRequired
from monitor.storage import Store
from monitor.worker import MonitorWorker


def test_checks_persist_and_stale_ack_does_not_hide_new_warning(tmp_path):
    path = tmp_path / "monitor.db"
    store = Store(path)
    group = Group("Jobs", "https://www.facebook.com/groups/1")
    store.record_scan_check(group, "error", "failed", 3)
    old = store.scan_checks()[0]
    store.record_scan_check(group, "pending", "not started")
    assert store.scan_checks()[0]["reason"] == "failed"
    store.record_scan_check(group, "warning", "limit", 20)
    store.resolve_scan_check(group.url, old["revision"])
    reopened = Store(path)
    row = reopened.scan_checks()[0]
    assert row["read_count"] == 20
    reopened.resolve_scan_check(group.url, row["revision"])
    assert reopened.scan_checks() == []
    reopened.record_scan_check(group, "warning", "limit", 20)
    assert len(reopened.scan_checks()) == 1


def test_session_failure_keeps_unvisited_groups_visible(tmp_path, monkeypatch):
    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)
    settings = Settings(groups=[Group(str(i), f"https://www.facebook.com/groups/{i}")
                                for i in range(1, 4)], auto_export=False)
    monkeypatch.setattr("monitor.worker.open_browser", lambda *args: nullcontext(object()))

    def fail(*args):
        raise SessionRequired("login required")

    monkeypatch.setattr("monitor.worker.read_group", fail)
    with pytest.raises(SessionRequired):
        worker.scan_once(settings)
    rows = {r["group_name"]: r for r in worker.store.scan_checks()}
    assert rows["1"]["severity"] == "error"
    assert rows["2"]["severity"] == rows["3"]["severity"] == "pending"


def test_reader_report_saved_with_actual_read_count(tmp_path, monkeypatch):
    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)
    monkeypatch.setattr("monitor.worker.open_browser", lambda *args: nullcontext(object()))

    def scrape(context, group, keywords, limit, stop, emit, on_post):
        emit("scan_report", {"severity": "warning", "reason": "limit", "read_count": 17})

    monkeypatch.setattr("monitor.worker.read_group", scrape)
    worker.scan_once(Settings(groups=[Group("Jobs", "https://www.facebook.com/groups/1")],
                              auto_export=False))
    assert worker.store.scan_checks()[0]["read_count"] == 17


def test_checks_panel_acknowledges_and_returns_to_posts(tmp_path):
    from monitor.app import MonitorApp

    app = MonitorApp(tmp_path)
    app.withdraw()
    try:
        app.store.record_scan_check(Group("Jobs", "https://www.facebook.com/groups/1"),
                                    "warning", "limit", 20)
        app.open_checks()
        assert len(app.checks_panel.listing.winfo_children()) == 1
        app.checks_panel.resolve(app.store.scan_checks()[0])
        assert not app.checks_panel.listing.winfo_children()
        assert app.checks_button.cget("text").endswith("(0)")
        app.checks_panel.back()
        assert app.results_panel.winfo_manager() == "grid"
    finally:
        app.destroy()


def test_info_clears_pending_but_preserves_unreviewed_errors(tmp_path):
    store = Store(tmp_path / "monitor.db")
    group = Group("Jobs", "https://www.facebook.com/groups/1")
    store.record_scan_check(group, "pending", "waiting")
    store.record_scan_check(group, "info", "limit", 20)
    assert store.scan_checks() == []
    store.record_scan_check(group, "error", "timeout", 3)
    store.record_scan_check(group, "info", "limit", 20)
    assert store.scan_checks()[0]["reason"] == "timeout"


def test_legacy_limit_only_warnings_retired(tmp_path):
    path = tmp_path / "monitor.db"
    store = Store(path)
    reason = "Chạm giới hạn bài; có thể còn bài phía dưới"
    store.record_scan_check(Group("1", "https://www.facebook.com/groups/1"), "warning", reason, 20)
    store.record_scan_check(Group("2", "https://www.facebook.com/groups/2"), "warning",
                            "1 thẻ thiếu nội dung/link; " + reason, 19)
    rows = Store(path).scan_checks()
    assert len(rows) == 1
    assert rows[0]["group_name"] == "2"
