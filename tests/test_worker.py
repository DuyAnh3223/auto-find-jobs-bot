from contextlib import nullcontext
from queue import Empty
from threading import Event

from monitor.core import Group, Post, Settings
from monitor.facebook import SessionRequired
from monitor.storage import Store
from monitor.worker import MonitorWorker


def test_scan_continues_after_group_error_and_deduplicates(tmp_path, monkeypatch):
    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)
    settings = Settings(
        groups=[
            Group("bad", "https://www.facebook.com/groups/1"),
            Group("good", "https://www.facebook.com/groups/2"),
        ]
    )
    monkeypatch.setattr("monitor.worker.open_browser", lambda *args: nullcontext(object()))

    def scrape(context, group, keywords, limit, stop, emit, on_post):
        if group.name == "bad":
            raise RuntimeError("unavailable")
        on_post(Post(group.url + "/posts/10", group.name, group.url, "Java Intern", ["java intern"]))

    monkeypatch.setattr("monitor.worker.read_group", scrape)
    worker.scan_once(settings)
    worker.scan_once(settings)
    assert worker.store.count() == 1
    assert (tmp_path / "exports" / "results.xlsx").exists()


def test_session_failure_stops_scheduler(tmp_path, monkeypatch):
    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)

    def expired(settings):
        raise SessionRequired("login required")

    monkeypatch.setattr(worker, "scan_once", expired)
    assert worker.start(Settings())
    worker.thread.join(timeout=3)
    assert not worker.running
    events = []
    while True:
        try:
            events.append(worker.events.get_nowait())
        except Empty:
            break
    assert ("error", "login required") in events
    assert not any(kind == "waiting" for kind, _ in events)


def test_all_groups_failed_preserves_existing_export(tmp_path, monkeypatch):
    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)
    target = tmp_path / "exports" / "results.xlsx"
    target.parent.mkdir()
    target.write_bytes(b"previous results")
    monkeypatch.setattr("monitor.worker.open_browser", lambda *args: nullcontext(object()))

    def fail(*args):
        raise RuntimeError("no readable cards")

    monkeypatch.setattr("monitor.worker.read_group", fail)
    worker.scan_once(Settings(groups=[Group("group", "https://www.facebook.com/groups/1")]))
    assert target.read_bytes() == b"previous results"


def test_partial_failure_exports_new_and_refreshed_posts(tmp_path, monkeypatch):
    from openpyxl import load_workbook

    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)
    monkeypatch.setattr("monitor.worker.open_browser", lambda *args: nullcontext(object()))
    settings = Settings(groups=[Group("group", "https://www.facebook.com/groups/1")])
    contents = iter(["Java first content", "Java updated content"])

    def partial(context, group, keywords, limit, stop, emit, on_post):
        on_post(Post(group.url + "/posts/10", group.name, group.url, next(contents), ["java"]))
        raise RuntimeError("feed interrupted after save")

    monkeypatch.setattr("monitor.worker.read_group", partial)
    for expected in ["Java first content", "Java updated content"]:
        worker.scan_once(settings)
        book = load_workbook(tmp_path / "exports" / "results.xlsx")
        assert book.active["I2"].value == expected
        book.close()
    assert worker.store.count() == 1


def test_stop_interrupts_interval_and_prevents_overlapping_start(tmp_path, monkeypatch):
    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)
    entered, release = Event(), Event()
    calls = []

    def scan(settings):
        calls.append(1)
        entered.set()
        release.wait(2)

    monkeypatch.setattr(worker, "scan_once", scan)
    assert worker.start(Settings())
    assert entered.wait(2)
    assert not worker.start(Settings())
    release.set()
    worker.stop()
    worker.thread.join(timeout=3)
    assert not worker.running
    assert calls == [1]


def test_interval_is_start_to_start_without_catchup_burst(tmp_path, monkeypatch):
    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)
    durations = []

    class WaitOnce:
        def is_set(self):
            return False

        def wait(self, duration):
            durations.append(duration)
            return True

    worker.stop_event = WaitOnce()
    monkeypatch.setattr(worker, "scan_once", lambda settings: None)
    clock = iter([0, 15, 0, 1300])
    monkeypatch.setattr("monitor.worker.time.monotonic", lambda: next(clock))
    worker._run(Settings(interval_minutes=20), "scan")
    worker._run(Settings(interval_minutes=20), "scan")
    assert durations == [1185, 1200]
