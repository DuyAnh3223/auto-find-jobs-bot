from monitor.core import Settings
from monitor.storage import Store


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
