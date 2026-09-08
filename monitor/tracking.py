from datetime import datetime
from urllib.parse import urlsplit

STATUSES = [
    "Đang xem xét",
    "Đã ứng tuyển",
    "Đã hẹn phỏng vấn",
    "Đã phỏng vấn",
    "Nhận offer",
    "Bị từ chối",
    "Đã rút",
]
FIELDS = {
    "company": "Tên công ty *",
    "position": "Vị trí ứng tuyển *",
    "applied_date": "Ngày ứng tuyển (DD/MM/YYYY)",
    "interview_at": "Lịch phỏng vấn (DD/MM/YYYY HH:MM, giờ máy tính)",
    "interview_location": "Địa điểm / link phỏng vấn",
    "contact_name": "Người liên hệ / HR",
    "email": "Email liên hệ",
    "phone": "Điện thoại / Zalo",
    "source_url": "Link tin tuyển dụng",
}


def validate_application(value):
    result = {key: str(value.get(key, "")).strip() for key in (*FIELDS, "notes", "status")}
    if result["status"] != "Đang xem xét" and (not result["company"] or not result["position"]):
        raise ValueError("Hãy nhập tên công ty và vị trí ứng tuyển.")
    if result["status"] not in STATUSES:
        raise ValueError("Trạng thái ứng tuyển không hợp lệ.")
    for key, pattern in (("applied_date", "%d/%m/%Y"), ("interview_at", "%d/%m/%Y %H:%M")):
        if result[key]:
            try:
                result[key] = datetime.strptime(result[key], pattern).strftime(pattern)
            except ValueError:
                raise ValueError(f"{FIELDS[key]}: ngày hoặc giờ không hợp lệ.") from None
    return result


def source_key(url):
    """Ignore Facebook share parameters when matching existing application links."""
    try:
        parsed = urlsplit(url.strip())
        host = (parsed.hostname or "").lower()
        if host in {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com"}:
            return "facebook.com" + parsed.path.rstrip("/").replace("/permalink/", "/posts/")
        return url.strip()
    except ValueError:
        return url.strip()
