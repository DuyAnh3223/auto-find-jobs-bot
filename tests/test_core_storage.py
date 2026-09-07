import unicodedata
from dataclasses import replace

import pytest

from monitor.core import Group, Post, Settings, group_url, match_keywords, post_url
from monitor.storage import Store


def test_keywords_case_unicode_whitespace_multiple():
    content = unicodedata.normalize("NFD", "Tuyển JAVA\n INTERN, biết Spring\u00a0Boot. Thực tập backend")
    assert match_keywords(
        content, ["java intern", "spring boot", "THỰC TẬP backend", "flutter", "JAVA INTERN", ""]
    ) == ["java intern", "spring boot", "THỰC TẬP backend"]
    assert match_keywords("tuyen java", ["tuyển java"]) == []  # accents remain meaningful


@pytest.mark.parametrize(
    "url",
    [
        "https://facebook.com.evil.com/groups/123",
        "http://facebook.com/groups/123",
        "https://evil.com/groups/123",
        "https://user:pass@facebook.com/groups/123",
        "file:///groups/123",
        "https://facebook.com/groups/123/posts/1",
        "https://facebook.com/groups/feed",
        "https://facebook.com:123/groups/123",
    ],
)
def test_reject_invalid_groups(url):
    with pytest.raises(ValueError):
        group_url(url)


def test_canonical_urls_keep_query_identity():
    group = "https://www.facebook.com/groups/123"
    assert group_url("https://m.facebook.com/groups/123/?ref=share") == group
    expected = group + "/posts/456"
    assert post_url("/groups/123/permalink/456/?__cft__=tracking", group) == expected
    assert post_url("https://m.facebook.com/permalink.php?story_fbid=456&id=123&ref=share", group) == expected
    assert post_url("/groups/123/posts/pfbidAbcDEF/?ref=share", group) == group + "/posts/pfbidAbcDEF"
    assert post_url("/groups/999/posts/456", group) is None
    assert post_url("https://evil.com/groups/123/posts/456", group) is None


def test_settings_validation_and_roundtrip():
    value = Settings(groups=[Group("IT Jobs", "https://facebook.com/groups/123/")])
    value.validate(for_scan=True)
    assert Settings.from_dict(value.to_dict()) == value
    with pytest.raises(ValueError):
        replace(value, interval_minutes=0).validate()
    with pytest.raises(ValueError):
        replace(value, groups=[]).validate(for_scan=True)
    with pytest.raises(ValueError):
        replace(value, keywords=[]).validate(for_scan=True)


def sample_post(**kwargs):
    return Post(
        "https://www.facebook.com/groups/123/posts/456",
        "IT Jobs HCM",
        "https://www.facebook.com/groups/123",
        "Tuyển Java Intern",
        ["java intern"],
        **kwargs,
    )


def test_store_dedup_survives_restart_preserves_first_detection(tmp_path):
    path = tmp_path / "monitor.db"
    first = sample_post(detected_at="2026-09-07T07:35:00+00:00")
    store = Store(path)
    assert store.save_post(first)
    store = Store(path)
    assert not store.save_post(
        replace(
            first,
            content="JAVA INTERN biết Spring Boot",
            keywords=["java intern", "spring boot"],
            detected_at="2026-09-08T07:35:00+00:00",
        )
    )
    assert store.count() == 1
    row = store.posts()[0]
    assert row["detected_at"] == first.detected_at
    assert row["content"] == "JAVA INTERN biết Spring Boot"
    assert "spring boot" in row["keywords"]
    assert row["posted_at"] is None


def test_store_config_and_literal_search_pagination(tmp_path):
    store = Store(tmp_path / "monitor.db")
    value = Settings(groups=[Group("Group A", "https://www.facebook.com/groups/123", False)])
    store.save_settings(value)
    assert Store(store.path).load_settings() == value
    for i in range(3):
        store.save_post(
            replace(sample_post(), url=f"https://www.facebook.com/groups/123/posts/{i}", content=f"Java {i}")
        )
    assert len(store.posts(limit=2)) == 2
    assert len(store.posts(limit=2, offset=2)) == 1
    assert store.count("Java") == 3
    assert store.count("%") == 0
    assert store.count("' OR 1=1 --") == 0
