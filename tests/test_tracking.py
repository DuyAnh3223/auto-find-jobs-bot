import pytest

from monitor.core import Post
from monitor.storage import Store
from monitor.tracking import STATUSES, validate_application


def application(**changes):
    return {
        "company": " Công ty ABC ",
        "position": "Java Fresher",
    "status": STATUSES[0],
        "applied_date": "08/09/2026",
        "interview_at": "10/09/2026 14:30",
        "contact_name": "HR An",
        "phone": "0900123456",
        "email": "hr@example.com",
        "notes": "Vòng 1 online\nChuẩn bị CV",
        **changes,
    }


def test_tracking_persists_and_updates_without_scan_overwrite(tmp_path):
    path = tmp_path / "monitor.db"
    store = Store(path)
    identity = store.save_application(application())
    reopened = Store(path)
    first = reopened.applications()[0]
    assert first["company"] == "Công ty ABC"
    assert first["phone"] == "0900123456"
    assert first["interview_at"] == "10/09/2026 14:30"
    assert first["notes"] == "Vòng 1 online\nChuẩn bị CV"
    reopened.save_application(application(status=STATUSES[2]), identity)
    reopened.save_post(
        Post(
            "https://www.facebook.com/groups/1/posts/2",
            "IT",
            "https://www.facebook.com/groups/1",
            "Java job updated",
            ["java"],
        )
    )
    updated = Store(path).applications()
    assert len(updated) == 1
    assert updated[0]["status"] == STATUSES[2]
    assert updated[0]["created_at"] == first["created_at"]
    reopened.delete_application(identity)
    assert reopened.applications() == []
    assert reopened.count() == 1


@pytest.mark.parametrize(
    "change",
    [
        {"company": " "},
        {"position": ""},
        {"status": "unknown"},
        {"applied_date": "31/02/2026"},
        {"interview_at": "10/09/2026 25:00"},
    ],
)
def test_invalid_application_is_rejected(change):
    value = application(status="Đã ứng tuyển")
    value.update(change)
    with pytest.raises(ValueError):
        validate_application(value)


def test_manual_application_can_omit_interview_and_contact(tmp_path):
    store = Store(tmp_path / "monitor.db")
    store.save_application({"company": "ABC", "position": "Backend", "status": STATUSES[0]})
    assert store.applications()[0]["interview_at"] == ""
    with pytest.raises(ValueError):
        store.save_application(application(), 999)


def test_consideration_can_be_saved_before_company_and_position(tmp_path):
    store = Store(tmp_path / "monitor.db")
    identity = store.save_application({"status": "Đang xem xét", "source_url": "https://example.test/job"})
    saved = store.applications()[0]
    assert saved["id"] == identity
    assert saved["company"] == ""
    with pytest.raises(ValueError):
        store.save_application({**saved, "status": "Đã ứng tuyển"}, identity)


def test_restore_application_keeps_identity_for_session_undo(tmp_path):
    store = Store(tmp_path / "monitor.db")
    identity = store.save_application(application(status="Đã ứng tuyển"))
    deleted = store.applications()[0]
    store.delete_application(identity)
    store.restore_application(deleted)
    restored = store.applications()[0]
    assert restored["id"] == identity
    assert restored["company"] == "Công ty ABC"


def test_post_badge_links_legacy_url_and_duplicates_and_updates(tmp_path):
    store = Store(tmp_path / "monitor.db")
    first = "https://www.facebook.com/groups/1/posts/10"
    second = "https://www.facebook.com/groups/2/posts/20"
    for url, name, content in (
        (first, "A", "Java intern"),
        (second, "GroupBeta", "JAVA  INTERN"),
        (first + "1", "A", "Different job"),
    ):
        store.save_post(Post(url, name, url.split("/posts/")[0], content, ["java"]))
    identity = store.save_application(application(source_url=first + "/?ref=share"))
    rows = Store(store.path).grouped_posts(search="GroupBeta")
    assert len(rows) == 1
    assert rows[0]["application_ids"] == [identity]
    assert rows[0]["application_status"] == STATUSES[0]
    assert store.grouped_posts(search="Different")[0]["application_status"] == ""
    store.save_application(application(source_url=first, status=STATUSES[1]), identity)
    assert store.grouped_posts(search="GroupBeta")[0]["application_status"] == STATUSES[1]
    store.delete_application(identity)
    assert store.grouped_posts(search="GroupBeta")[0]["application_ids"] == []


def test_post_processing_keeps_bot_evaluation_separate_from_skip(tmp_path):
    store = Store(tmp_path / "monitor.db")
    post = Post(
        "https://www.facebook.com/groups/1/posts/10",
        "Java",
        "https://www.facebook.com/groups/1",
        "Java internship",
        ["java"],
        bot_status="review",
    )
    store.save_post(post)
    row = store.grouped_posts(category="all")[0]
    assert (row["evaluation"], row["processing"]) == ("review", "unprocessed")
    store.set_user_decision(row["content_hash"], "skipped")
    row = store.grouped_posts(category="all")[0]
    assert (row["evaluation"], row["processing"]) == ("review", "skipped")
    store.set_user_decision(row["content_hash"], None)
    store.save_application({"status": "Đang xem xét", "source_url": post.url})
    row = store.grouped_posts(category="all")[0]
    assert (row["evaluation"], row["processing"]) == ("review", "tracked")
