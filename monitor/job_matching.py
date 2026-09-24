"""Deterministic job matching for the SWE/IT-support HCM profile."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field

from monitor import job_taxonomy as taxonomy

CLASSIFIER_VERSION = "job-profile-4"


def criteria_fingerprint(settings=None) -> str:
    families = sorted(getattr(settings, "job_families", [taxonomy.SWE, taxonomy.IT_SUPPORT]))
    return hashlib.sha256(json.dumps([CLASSIFIER_VERSION, families]).encode()).hexdigest()[:16]


def fold(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("–", "-").replace("—", "-").replace("−", "-")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Build a boundary-aware pattern without treating punctuation as a word."""
    pieces = re.findall(r"[\w]+|[^\w\s]", fold(phrase), flags=re.UNICODE)
    if not pieces:
        return re.compile(r"(?!)")
    body = r"\s*".join(re.escape(piece) for piece in pieces)
    return re.compile(rf"(?<![\w]){body}(?![\w])", re.IGNORECASE)


def find_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
    folded = fold(text)
    return [phrase for phrase in phrases if _phrase_pattern(phrase).search(folded)]


def candidate_keyword_hits(text: str, keywords: list[str] | tuple[str, ...]) -> list[str]:
    """Strict prefilter matching; unlike the legacy matcher, intern != internal."""
    folded = fold(text)
    hits, seen = [], set()
    for keyword in keywords:
        value = str(keyword).strip()
        if not value:
            continue
        normalized = fold(value)
        if normalized in seen:
            continue
        if _phrase_pattern(value).search(folded):
            hits.append(value)
            seen.add(normalized)
    return hits


def candidate_keywords() -> list[str]:
    return list(taxonomy.CANDIDATE_PHRASES)


def _clean_title_prefix(line: str) -> str:
    value = fold(line)
    value = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", value)
    recruitment = re.search(r"(?<![\w])(?:tuyen(?: dung)?|hiring|recruiting)(?![\w])", value)
    if recruitment:
        value = value[recruitment.end():]
    return re.sub(r"^\s*(?:[-:–—]|gap\b)*\s*", "", value)


def _technology_title(line: str) -> bool:
    value = _clean_title_prefix(line)
    return any(
        (match := _phrase_pattern(phrase).search(value)) is not None and match.start() == 0
        for phrase in taxonomy.TECHNOLOGY_PHRASES
    )


def _technology_entry_title(line: str) -> bool:
    """Accept title-shaped aliases such as ``Java Intern`` without promoting body keywords."""
    value = _clean_title_prefix(line)
    technology = [match for phrase in taxonomy.TECHNOLOGY_PHRASES for match in [_phrase_pattern(phrase).search(value)] if match]
    entry = [match for phrase in taxonomy.ENTRY_PHRASES for match in [_phrase_pattern(phrase).search(value)] if match]
    for first, second in ((technology, entry), (entry, technology)):
        for left in first:
            if left.start() != 0:
                continue
            for right in second:
                between = value[left.end():right.start()]
                if right.start() >= left.end() and len(re.findall(r"\w+", between)) <= 2:
                    return True
    return False


@dataclass
class Evidence:
    field: str
    snippet: str
    block_index: int


@dataclass
class JobMatch:
    title: str
    family: str | None
    level: str
    location: str
    status: str
    reasons: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class MatchResult:
    status: str
    reason_codes: list[str] = field(default_factory=list)
    matched_families: list[str] = field(default_factory=list)
    jobs: list[JobMatch] = field(default_factory=list)
    classifier_version: str = CLASSIFIER_VERSION

    @property
    def matched_keywords(self) -> list[str]:
        values: list[str] = []
        for job in self.jobs:
            for evidence in job.evidence:
                if evidence.field in {"family", "level"} and evidence.snippet not in values:
                    values.append(evidence.snippet)
        return values

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))


def _line_title_score(line: str) -> tuple[str | None, list[str]]:
    value = fold(line)
    if not value:
        return None, []
    families: list[str] = []
    strong_swe = find_phrases(value, taxonomy.SWE_STRONG_PHRASES)
    strong_it = find_phrases(value, taxonomy.IT_STRONG_PHRASES)
    context_swe = find_phrases(value, taxonomy.SWE_CONTEXT_PHRASES)
    context_it = find_phrases(value, taxonomy.IT_CONTEXT_PHRASES)
    if _non_target_role_line(line):
        return line.strip(), []

    # Business Developer, business development and business dev are common false positives.
    is_business = bool(re.search(r"\b(?:business|sales|account)\s+(?:development|developer|dev)\b", value))
    has_generic_developer = bool(re.search(r"(?<![\w])(?:developer|dev)(?![\w])", value))
    context_role = find_phrases(
        value,
        (
            "backend",
            "back-end",
            "frontend",
            "front-end",
            "full stack",
            "fullstack",
            "full-stack",
            "lập trình",
            "lap trinh",
            "phần mềm",
            "phan mem",
            "swe",
            "sde",
        ),
    )
    if (strong_swe or (context_swe and not is_business and (has_generic_developer or context_role))) and not is_business:
        families.append(taxonomy.SWE)
    if strong_it or context_it:
        families.append(taxonomy.IT_SUPPORT)
    if not families and _technology_entry_title(line):
        families.append(taxonomy.SWE)
    if not families:
        return None, []
    # Prefer a specific title line over the entire bullet/details line.
    title = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
    return title[:240], list(dict.fromkeys(families))


def _non_target_role_line(line: str) -> bool:
    value = fold(line)
    if re.search(r"skills?:|ky nang|phoi hop|work with|collaborat|requirements?:|yeu cau", value):
        value = re.split(r"skills?:|ky nang|phoi hop|work with|collaborat|requirements?:|yeu cau", value)[0]
    if _technology_entry_title(line) or re.search(
        r"backend|frontend|software (?:engineer|developer)|java developer|lap trinh vien|phat trien phan mem|ky su phan mem|lap trinh",
        value,
    ):
        return False
    return bool(
        re.search(
            r"(?<![\w])(?:marketing|sales|business|hr|human resources|customer support|customer service|"
            r"cham soc khach hang|kinh doanh|ke toan|accounting|finance|qa|tester|test engineer|designer|"
            r"data analyst|business analyst|operations?|content|product|recruiter|talent acquisition)(?![\w])",
            value,
        )
    )


def _candidate_blocks(text: str) -> list[tuple[str, int, int, list[str]]]:
    lines = re.split(r"\n|;", text) or [text]
    candidates: list[tuple[int, str, list[str]]] = []
    for index, line in enumerate(lines):
        if re.match(r"\s*(?:[-•*]\s*)?(?:skills?|requirements?|benefits?|ky nang|yeu cau|quyen loi|nhiem vu)\s*:", fold(line)):
            continue
        title, families = _line_title_score(line)
        if title:
            candidates.append((index, title, families))
        elif _non_target_role_line(line):
            candidates.append((index, line.strip()[:240], []))
    if not candidates:
        # A plain one-line post such as "Java Intern HCM" remains testable and
        # reviewable, while technology-only posts will not become suitable.
        title, families = _line_title_score(text)
        if title:
            candidates = [(0, title, families)]
        elif _technology_title(text):
            candidates = [(0, text.strip()[:240], [taxonomy.SWE])]
    blocks = []
    for position, (start, title, families) in enumerate(candidates):
        end = candidates[position + 1][0] if position + 1 < len(candidates) else len(lines)
        blocks.append((title, start, end, families))
    return [("\n".join(lines[start:end]), start, end, families) for _, start, end, families in blocks]


def _locations(text: str) -> set[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    explicit_indexes = [
        index
        for index, line in enumerate(lines)
        if re.search(
            r"dia diem|noi lam viec|lam viec tai|work location|working location|job location|office location",
            fold(line),
        )
    ]
    if explicit_indexes:
        selected = []
        for index in explicit_indexes:
            selected.append(lines[index])
            if lines[index].rstrip().endswith(":") and index + 1 < len(lines):
                selected.append(lines[index + 1])
        value = fold(" ".join(selected))
    else:
        value = fold(text)
    locations: set[str] = set()
    if find_phrases(value, taxonomy.HCM_LOCATION_PHRASES):
        locations.add("hcm")
    if find_phrases(value, taxonomy.OUTSIDE_LOCATION_PHRASES):
        locations.add("outside")
    return locations


def _location_for_block(block: str, full_text: str, block_count: int) -> str:
    local = _locations(block)
    if local == {"hcm"}:
        return "hcm"
    if local == {"outside"}:
        return "outside"
    if local == {"hcm", "outside"}:
        return "unknown"
    # Only an explicitly scoped common location can be inherited across jobs.
    shared_text = full_text if block_count == 1 else "\n".join(
        line for line in full_text.splitlines()
        if re.search(r"(?:all (?:positions|roles)|tat ca vi tri|dia diem chung|common work location)", fold(line))
    )
    shared = _locations(shared_text)
    if len(shared) == 1:
        return next(iter(shared))
    return "unknown"


def _entry_level(block: str, title: str) -> tuple[str, list[str], bool]:
    value = fold(block)
    title_value = re.split(r"mentored|mentor|duoc|huong dan|guided|coached", fold(title))[0]
    evidence = find_phrases(value, taxonomy.ENTRY_PHRASES)
    strong_entry = bool(evidence)
    senior_title = bool(re.search(r"(?<![\w])(?:senior|lead|principal|manager)(?![\w])", title_value))
    if senior_title:
        return "senior", evidence, True
    if re.search(r"(?:khong (?:nhan|tuyen|chap nhan)|no|not accepting)\s+(?:intern\w*|fresh\w*)", value):
        return "conflict", evidence, True
    # Experience requirements are parsed independently from the entry marker;
    # a senior-only developer post often has no "intern/fresher" word at all.
    for raw_clause in re.split(r"[\n;]", block):
        clause = fold(raw_clause)
        for match in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:[-]|to|den)?\s*(\d+)?\s*\+?\s*(nam|years?|months?|thang)\b", clause):
            before = clause[max(0, match.start()-45):match.start()]
            after = clause[match.end():match.end()+35]
            if re.search(r"preferred|preferably|uu tien|advantage|nice to have|loi the|duoi|less than|toi da", before + after):
                continue
            if float(match[1]) > 0 and (
                re.search(r"minimum|at least|required|yeu cau|bat buoc|toi thieu|kinh nghiem|experience", before + after)
                or match[2]
            ):
                return "conflict", evidence, True
    if strong_entry:
        # A senior mentioned as a mentor is allowed; only explicit title and
        # required-experience evidence above can make the block conflicting.
        return "entry", evidence, False
    if re.search(r"(?<![\w])junior(?![\w])|(?<![\w])junior-level(?![\w])", value):
        return "junior", [], False
    if re.search(r"\b(?:0|<\s*1)\s*(?:-|to|đến)\s*1\s*(?:năm|nam|years?|year)\b", value):
        return "entry", [], False
    if re.search(r"(?<![\w])(?:senior|lead|principal|manager)(?![\w])", title_value):
        return "senior", [], True
    return "unknown", [], False


def _job_status(family: str | None, level: str, location: str, it_tasks_unclear: bool = False) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if family is None:
        return "unsuitable", ["no_target_family"]
    if level == "conflict" or level == "senior":
        return "unsuitable", ["senior_or_experience_conflict"]
    if it_tasks_unclear:
        reasons.append("it_tasks_unclear")
    if level not in {"entry"}:
        reasons.append("entry_level_unclear")
    if location == "outside":
        return "unsuitable", ["outside_hcm"]
    if location != "hcm":
        reasons.append("location_unclear")
    if not reasons and level == "entry" and location == "hcm":
        return "suitable", []
    return "review", reasons


def classify_job(text: str, settings=None) -> MatchResult:
    """Classify a post without SQLite, browser, Tk, or network dependencies."""
    opening = next((line for line in text.splitlines() if line.strip()), "")
    if not text or (
        find_phrases(opening, taxonomy.OBVIOUS_NON_JOB_PHRASES)
        and not find_phrases(opening, taxonomy.RECRUITMENT_PHRASES)
    ):
        return MatchResult("unsuitable", ["not_a_job_post"])
    blocks = _candidate_blocks(text)
    if not blocks:
        return MatchResult("unsuitable", ["no_target_family"])

    jobs: list[JobMatch] = []
    for block_index, (block, start, _end, families) in enumerate(blocks):
        title = next((line.strip() for line in block.splitlines() if line.strip()), block[:240].strip())
        title = re.split(r"\s*(?:,|;|\s+-\s+)\s*", title, maxsplit=1)[0].strip()
        family = families[0] if len(families) == 1 else None
        # IT intern/TTS IT becomes useful only when the block describes IT work.
        if taxonomy.IT_SUPPORT in families and taxonomy.SWE in families:
            family = taxonomy.IT_SUPPORT if find_phrases(
                block, ("pc", "máy tính", "may tinh", "mạng", "mang", "windows", "account", "người dùng", "nguoi dung")
            ) else taxonomy.SWE

        it_tasks_unclear = False
        if family == taxonomy.IT_SUPPORT:
            has_strong_it_title = bool(find_phrases(
                title, ("it support", "it helpdesk", "it help desk", "desktop support", "ho tro cntt", "end user support")
            ))
            has_it_tasks = bool(find_phrases(
                block, (
                    "may tinh", "máy tính", "windows", "network", "mang", "mạng",
                    "pc", "tai khoan", "tài khoản", "nguoi dung", "người dùng",
                    "cai win", "cài win", "phan cung", "phần cứng", "may in", "máy in"
                )
            ))
            if not has_strong_it_title and not has_it_tasks:
                # Distinguish explicit IT/CNTT roles from generic technical support.
                is_explicit_it = bool(
                    find_phrases(
                        title,
                        (
                            "it intern", "it fresher", "fresher it", "tts it", "it tts",
                            "thực tập sinh it", "thuc tap sinh it", "thực tập it", "thuc tap it",
                            "thực tập sinh cntt", "thuc tap sinh cntt", "thực tập cntt", "thuc tap cntt",
                            "tts cntt", "fresher cntt", "cntt fresher",
                            "thực tập sinh công nghệ thông tin", "thuc tap sinh cong nghe thong tin",
                            "thực tập công nghệ thông tin", "thuc tap cong nghe thong tin",
                            "fresher công nghệ thông tin", "fresher cong nghe thong tin",
                            "tts cong nghe thong tin", "tts công nghệ thông tin",
                            "nhân viên it", "nhan vien it", "it staff", "it officer",
                            "kỹ thuật it", "ky thuat it", "nhân viên cntt", "nhan vien cntt",
                            "kỹ thuật cntt", "ky thuat cntt", "công nghệ thông tin", "cong nghe thong tin",
                            "cntt", "kỹ thuật pc", "ky thuat pc", "pc support",
                        ),
                    )
                    or re.search(r"(?<![\w])(?:it|cntt)(?![\w])", fold(title))
                )
                if is_explicit_it:
                    it_tasks_unclear = True
                else:
                    family = None

        if family not in getattr(settings, "job_families", [taxonomy.SWE, taxonomy.IT_SUPPORT]):
            family = None
        level, level_hits, conflict = _entry_level(block, title)
        location = _location_for_block(block, text, len(blocks))
        status, reasons = _job_status(family, level, location, it_tasks_unclear)
        if conflict and "senior_or_experience_conflict" not in reasons:
            reasons.append("senior_or_experience_conflict")
            status = "unsuitable"
        evidence: list[Evidence] = []
        if family:
            evidence.append(Evidence("family", title, block_index))
        for marker in level_hits:
            evidence.append(Evidence("level", marker, block_index))
        evidence.append(Evidence("location", location, block_index))
        jobs.append(JobMatch(title, family, level, location, status, reasons, evidence))

    suitable = [job for job in jobs if job.status == "suitable"]
    target_jobs = [job for job in jobs if job.family]
    if suitable:
        status = "suitable"
        reasons: list[str] = []
    elif target_jobs and any(job.status == "review" for job in target_jobs):
        status = "review"
        reasons = sorted({reason for job in target_jobs for reason in job.reasons})
    else:
        status = "unsuitable"
        reasons = sorted({reason for job in jobs for reason in job.reasons}) or ["no_suitable_target_job"]
    return MatchResult(status, reasons, list(dict.fromkeys(job.family for job in suitable if job.family)), jobs)
