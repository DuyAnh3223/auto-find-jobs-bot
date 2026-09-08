from threading import Event
from types import SimpleNamespace

import pytest

from monitor import facebook
from monitor.core import Group


@pytest.mark.parametrize("limit,batches,expected,rounds", [
    (10, [list(range(30))], 10, 1),
    (20, [list(range(30))], 20, 1),
    (80, [list(range(i * 5, i * 5 + 5)) for i in range(16)], 80, 16),
    (80, [[1]] * 6, 1, 6),
    (80, [[1]] * 5 + [[2]] * 6, 2, 11),
    (80, [[i] for i in range(40)], 40, 40),
])
def test_reader_limits(monkeypatch, limit, batches, expected, rounds):
    class Card:
        def __init__(self, identity):
            self.identity = identity

        def evaluate(self, *args):
            return False

    class Page:
        index = 0
        reads = 0
        scrolls = 0
        closed = False

        def goto(self, *args, **kwargs):
            pass

        def locator(self, *args):
            return self

        def filter(self, **kwargs):
            return self

        def count(self):
            return 1

        def element_handles(self):
            self.reads += 1
            return [Card(i) for i in batches[min(self.index, len(batches) - 1)]]

        def evaluate(self, *args):
            self.index += 1
            self.scrolls += 1

        def close(self):
            self.closed = True

    page = Page()
    for name in ["require_session", "pause", "require_card", "expand_card"]:
        monkeypatch.setattr(facebook, name, lambda *args: None)
    monkeypatch.setattr(facebook, "read_card", lambda card, page, url, stop: {
        "text": "No keyword match", "links": [{"href": f"{url}/posts/{card.identity}"}],
    })
    events = []
    facebook.read_group(SimpleNamespace(new_page=lambda: page),
                        Group("Jobs", "https://www.facebook.com/groups/123"),
                        ["java"], limit, Event(), lambda *event: events.append(event),
                        lambda post: pytest.fail("Nonmatching posts still count as progress"))
    report = next(value for kind, value in events if kind == "scan_report")
    assert report["read_count"] == expected
    assert report["severity"] == "info"
    assert page.reads == rounds
    assert page.scrolls == rounds - 1
    assert page.closed
