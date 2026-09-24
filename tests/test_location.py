import pytest

from monitor.core import Post, Settings, classify_content, job_location


@pytest.mark.parametrize("text,expected", [
    ("Java TP.HCM", "hcm"), ("Java TPHCM", "hcm"), ("Java HCMC", "hcm"),
    ("Hồ Chí Minh", "hcm"), ("Ho Chi Minh", "hcm"), ("Sài Gòn", "hcm"),
    ("Tuyển HN và HCM", "hcm"), ("Java HN", "outside"),
    ("Đà Nẵng", "outside"), ("Hải Phòng", "outside"),
    ("Java internship", "unknown"), ("TECHNOLOGY", "unknown"),
    ("Trụ sở HCM\nLàm việc tại Hà Nội", "outside"),
    ("Địa điểm làm việc:\nTP.HCM", "hcm"),
    ("Địa điểm làm việc: Hà Nội và HCM", "hcm"),
])
def test_location_detection(text, expected):
    assert job_location(text) == expected


def test_old_posts_are_filtered_without_rescanning(tmp_path):
    from monitor.app import MonitorApp

    app = MonitorApp(tmp_path)
    app.withdraw()
    try:
        for index, text in enumerate(["Java Intern HCM", "Java HN", "Java internship", "Java HCM senior 3 years"]):
            app.store.save_post(Post(f"https://www.facebook.com/groups/1/posts/{index}",
                                    "Jobs", "https://www.facebook.com/groups/1", text, ["java"],
                                    bot_status="unsuitable" if "senior" in text else "suitable"))
        assert app.filtered_rows() == []  # Legacy labels are not current evidence.
        app.evaluation_filter.set("Cần đánh giá lại")
        assert len(app.filtered_rows()) == 2
        app.store.reclassify_posts(apply=True)
        app.evaluation_filter.set("Phù hợp")
        assert [r["content"] for r in app.filtered_rows()] == ["Java Intern HCM"]
        app.evaluation_filter.set("Cần xem lại")
        app.location_filter.set("Chưa rõ địa điểm")
        assert [r["content"] for r in app.filtered_rows()] == ["Java internship"]
        app.location_filter.set("Tất cả")
        app.evaluation_filter.set("Tất cả")
        assert len(app.filtered_rows()) == 2
        app.store.save_post(Post("https://www.facebook.com/groups/1/posts/9", "Jobs",
                                "https://www.facebook.com/groups/1", "Java HCM review", ["java"],
                                bot_status="review"))
        app.store.reclassify_posts(apply=True)
        app.location_filter.set("HCM")
        app.evaluation_filter.set("Cần xem lại")
        assert [r["content"] for r in app.filtered_rows()] == ["Java HCM review"]
        app.evaluation_filter.set("Phù hợp")
        assert [r["content"] for r in app.filtered_rows()] == ["Java Intern HCM"]
        assert app.store.count() == 5
    finally:
        app.destroy()


def test_missing_location_still_checks_experience():
    settings = Settings(keywords=["java"], experience_keywords=["intern"])
    assert classify_content("Java senior 3 years", settings) == "unsuitable"
    assert classify_content("Java intern", settings) == "review"


def test_scan_discards_outside_posts_before_storage(tmp_path, monkeypatch):
    from contextlib import nullcontext

    from monitor.storage import Store
    from monitor.worker import MonitorWorker

    worker = MonitorWorker(Store(tmp_path / "monitor.db"), tmp_path)
    monkeypatch.setattr("monitor.worker.open_browser", lambda *args: nullcontext(object()))

    def scrape(context, group, keywords, limit, stop, emit, on_post):
        for index, text in enumerate([
            "Java HN", "Java HCM", "Java internship", "Java HN và HCM", "Java HCM senior 3 years"
        ]):
            on_post(Post(f"{group.url}/posts/{index}", group.name, group.url, text, ["java"]))

    from monitor.core import Group

    monkeypatch.setattr("monitor.worker.read_group", scrape)
    worker.scan_once(Settings(groups=[Group("Jobs", "https://www.facebook.com/groups/1")],
                              keywords=["java"], experience_keywords=["intern"], auto_export=False))
    assert {row["content"] for row in worker.store.posts()} == {
        "Java HCM", "Java internship", "Java HN và HCM",
    }
