import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlparse


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    haystack = normalize(text)
    matches, seen = [], set()
    for keyword in keywords:
        needle = normalize(keyword)
        if needle and needle not in seen and needle in haystack:
            matches.append(keyword.strip())
            seen.add(needle)
    return matches


def facebook_url(value: str):
    parsed = urlparse(urljoin("https://www.facebook.com/", value.strip()))
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com"}
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Chỉ chấp nhận link HTTPS thuộc facebook.com.")
    return parsed


def group_url(value: str) -> str:
    parsed = facebook_url(value)
    match = re.fullmatch(r"/groups/([A-Za-z0-9._-]+)/?", parsed.path)
    if not match or match[1] in {"feed", "discover", "joins", "create"}:
        raise ValueError("Nhập link group dạng https://www.facebook.com/groups/ten-hoac-id")
    return f"https://www.facebook.com/groups/{match[1]}"


def post_url(value: str, source: str) -> str | None:
    """Canonical URL; never discard story_fbid before extracting its identity."""
    try:
        parsed = facebook_url(value)
        source = group_url(source)
    except ValueError:
        return None
    match = re.fullmatch(r"/groups/([A-Za-z0-9._-]+)/(?:posts|permalink)/([A-Za-z0-9]+)/?", parsed.path)
    if match:
        # A shared post can point to a different group; don't attribute it to this one.
        if match[1] != source.rsplit("/", 1)[-1]:
            return None
        return f"{source}/posts/{match[2]}"
    query = parse_qs(parsed.query)
    identity = query.get("story_fbid", [""])[0]
    owner = query.get("id", [""])[0]
    if (
        parsed.path in {"/permalink.php", "/story.php"}
        and re.fullmatch(r"[A-Za-z0-9]+", identity)
        and owner == source.rsplit("/", 1)[-1]
    ):
        return f"{source}/posts/{identity}"
    return None


@dataclass
class Group:
    name: str
    url: str
    enabled: bool = True


@dataclass
class Settings:
    groups: list[Group] = field(default_factory=list)
    keywords: list[str] = field(
        default_factory=lambda: ["tuyển java", "java intern", "thực tập backend", "spring boot", "flutter"]
    )
    interval_minutes: int = 20
    max_posts: int = 30
    browser: str = "msedge"
    auto_export: bool = True

    def validate(self, for_scan: bool = False):
        if not 10 <= self.interval_minutes <= 1440:
            raise ValueError("Khoảng quét phải từ 10 đến 1440 phút.")
        if not 1 <= self.max_posts <= 100:
            raise ValueError("Giới hạn bài mỗi group phải từ 1 đến 100.")
        if self.browser not in {"chrome", "msedge"}:
            raise ValueError("Hãy chọn Chrome hoặc Edge.")
        urls = set()
        for group in self.groups:
            group.url = group_url(group.url)
            group.name = group.name.strip() or group.url.rsplit("/", 1)[-1]
            if group.url in urls:
                raise ValueError("Danh sách có group trùng link.")
            urls.add(group.url)
        self.keywords = list(dict.fromkeys(k.strip() for k in self.keywords if k.strip()))
        if for_scan and not any(g.enabled for g in self.groups):
            raise ValueError("Hãy thêm và bật ít nhất một group.")
        if for_scan and not self.keywords:
            raise ValueError("Hãy nhập ít nhất một từ khóa.")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["groups"] = [Group(**g) for g in data.get("groups", [])]
        settings = cls(**data)
        settings.validate()
        return settings


@dataclass
class Post:
    url: str
    group_name: str
    group_url: str
    content: str
    keywords: list[str]
    detected_at: str = field(default_factory=now_iso)
    posted_at: str | None = None
    posted_time_raw: str = ""
