import hashlib
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


def normalized_content(text: str) -> str:
    """Stable exact-duplicate key; keeps meaningful punctuation and words."""
    return normalize(text)


def content_hash(text: str) -> str:
    return hashlib.sha256(normalized_content(text).encode("utf-8")).hexdigest()


def job_location(text: str) -> str:
    """Text-only detection: missing location stays unknown, never assumed outside HCM."""
    folded = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    lines = folded.splitlines()
    explicit = [line for line in lines if re.search(
        r"dia diem lam viec|noi lam viec|lam viec tai|work location|working location|job location", line
    )]
    if explicit:
        for index, line in enumerate(lines[:-1]):
            if line in explicit and re.search(r":\s*$", line):
                explicit.append(lines[index + 1])
    scope = " ".join(explicit) if explicit else folded
    if re.search(
        r"(?<!\w)(?:hcm|hcmc|tp[.\s]*hcm|tp[.\s]*hcmc|ho\s*chi\s*minh|hochiminh|sai\s*gon|saigon)(?!\w)",
        scope,
    ):
        return "hcm"
    if re.search(
        r"(?<!\w)(?:ha\s*noi|hanoi|hn|da\s*nang|danang|hai\s*phong|haiphong|"
        r"can tho|hai duong|bac ninh|bac giang|quang ninh|nha trang|da lat|hue|"
        r"quy nhon|vinh|thanh hoa|nghe an)(?!\w)", scope
    ):
        return "outside"
    return "unknown"


def classify_content(
    text: str, settings: "Settings", matched_position_keywords: list[str] | None = None
) -> str:
    """Compatibility wrapper around the deterministic job profile classifier."""
    from monitor.job_matching import classify_job

    result = classify_job(text, settings)
    return result.status


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
    job_families: list[str] = field(default_factory=lambda: ["swe", "it_helpdesk_support"])
    keywords: list[str] = field(
        default_factory=lambda: [
            "software engineer",
            "software developer",
            "lập trình viên",
            "backend developer",
            "frontend developer",
            "full stack developer",
            "java developer",
            "it helpdesk",
            "it support",
            "desktop support",
            "service desk",
            "nhân viên IT",
        ]
    )
    location_keywords: list[str] = field(default_factory=list)
    experience_keywords: list[str] = field(default_factory=list)
    interval_minutes: int = 30
    max_posts: int = 20
    daily_deep_time: str = "07:00"
    daily_deep_posts: int = 60
    startup_schedule_version: int = 1
    browser: str = "msedge"
    auto_export: bool = True

    def validate(self, for_scan: bool = False):
        if not self.job_families or set(self.job_families) - {"swe", "it_helpdesk_support"}:
            raise ValueError("Hãy chọn SWE hoặc IT Helpdesk/Support.")
        if not 10 <= self.interval_minutes <= 1440:
            raise ValueError("Khoảng quét phải từ 10 đến 1440 phút.")
        if not 1 <= self.max_posts <= 100:
            raise ValueError("Giới hạn bài mỗi group phải từ 1 đến 100.")
        if not 1 <= self.daily_deep_posts <= 100:
            raise ValueError("Giới hạn lượt đầu ngày phải từ 1 đến 100.")
        try:
            datetime.strptime(self.daily_deep_time, "%H:%M")
        except ValueError:
            raise ValueError("Giờ lượt đầu ngày phải có dạng HH:MM.") from None
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
        self.location_keywords = list(dict.fromkeys(k.strip() for k in self.location_keywords if k.strip()))
        self.experience_keywords = list(
            dict.fromkeys(k.strip() for k in self.experience_keywords if k.strip())
        )
        if for_scan and not any(g.enabled for g in self.groups):
            raise ValueError("Hãy thêm và bật ít nhất một group.")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        if "startup_schedule_version" not in data:
            data.update(interval_minutes=30, max_posts=20, daily_deep_posts=60,
                        startup_schedule_version=1)
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
    bot_status: str = "suitable"
    content_hash: str | None = None
    classification_json: str | None = None
    classifier_version: str | None = None
    criteria_fingerprint: str | None = None
    classified_at: str | None = None
