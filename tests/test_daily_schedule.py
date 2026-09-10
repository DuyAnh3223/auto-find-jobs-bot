from monitor.core import Settings
from monitor.storage import Store
from monitor.worker import MonitorWorker


def test_daily_deep_scan_marker_is_idempotent(tmp_path):
    store = Store(tmp_path / "monitor.db")
    assert not store.deep_scan_completed("2026-09-08")
    store.mark_deep_scan_completed("2026-09-08")
    store.mark_deep_scan_completed("2026-09-08")
    assert store.deep_scan_completed("2026-09-08")
    assert not store.deep_scan_completed("2026-09-09")


def test_regular_and_daily_limits_are_independent():
    settings = Settings(max_posts=20, interval_minutes=45, daily_deep_posts=60, daily_deep_time="07:00")
    settings.validate()
    assert (settings.max_posts, settings.interval_minutes) == (20, 45)
    assert (settings.daily_deep_posts, settings.daily_deep_time) == (60, "07:00")


def test_each_process_starts_deep_even_on_same_day(tmp_path, monkeypatch):
    store = Store(tmp_path / "monitor.db")
    limits = []

    class TwoRounds:
        waits = 0

        def is_set(self):
            return False

        def wait(self, duration):
            self.waits += 1
            return self.waits >= 2

    for _ in range(2):
        worker = MonitorWorker(store, tmp_path)
        worker.stop_event = TwoRounds()

        def scan(settings, limit):
            limits.append(limit)
            return True

        monkeypatch.setattr(worker, "scan_once", scan)
        worker._run(Settings(), "scan")
        worker.stop_event = TwoRounds()
        worker._run(Settings(), "scan")
    assert limits == [60, 20, 20, 20, 60, 20, 20, 20]


def test_old_schedule_upgrades_once():
    settings = Settings.from_dict({"interval_minutes": 45, "max_posts": 80})
    assert (settings.interval_minutes, settings.max_posts, settings.daily_deep_posts) == (30, 20, 60)
    settings.interval_minutes = 40
    assert Settings.from_dict(settings.to_dict()).interval_minutes == 40
