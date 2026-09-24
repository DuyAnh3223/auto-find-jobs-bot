import json

import pytest

from monitor.job_matching import candidate_keyword_hits, classify_job


@pytest.mark.parametrize(
    ("text", "status", "family"),
    [
        ("Tuyển Java Backend Intern tại TP.HCM", "suitable", "swe"),
        ("Backend Intern tại TP.HCM", "suitable", "swe"),
        ("Frontend Fresher tại TP.HCM", "suitable", "swe"),
        ("Thực tập sinh lập trình React tại Hồ Chí Minh", "suitable", "swe"),
        ("Thực tập sinh phần mềm HCM", "suitable", "swe"),
        ("Thực tập sinh phát triển phần mềm HCM", "suitable", "swe"),
        ("Graduate Software Engineer HCM", "suitable", "swe"),
        ("SWE Intern HCM", "suitable", "swe"),
        ("SDE Intern HCM", "suitable", "swe"),
        ("Dev Intern HCM", "suitable", "swe"),
        ("IT Helpdesk Fresher - làm việc tại HCM", "suitable", "it_helpdesk_support"),
        (
            "TTS IT hỗ trợ máy tính, Windows, tài khoản và mạng tại TP HCM",
            "suitable",
            "it_helpdesk_support",
        ),
        ("IT Intern HCM", "review", "it_helpdesk_support"),
        ("IT Fresher HCM", "review", "it_helpdesk_support"),
        ("Thực tập sinh IT HCM", "review", "it_helpdesk_support"),
        ("Thực tập sinh công nghệ thông tin HCM", "review", "it_helpdesk_support"),
        ("Tuyển Business Developer Intern ngành bất động sản tại HCM", "unsuitable", None),
        ("Tuyển Customer Support Fresher cho dịch vụ vận chuyển tại HCM", "unsuitable", None),
        ("Tuyển Java Developer tại HCM; liên hệ internal recruitment team", "review", "swe"),
        ("Tuyển Java Developer tại HCM, yêu cầu tối thiểu 11 năm kinh nghiệm", "unsuitable", None),
        ("Tuyển Java Developer tại HCM, yêu cầu 4 năm kinh nghiệm", "unsuitable", None),
        ("Tuyển Java Developer tại HCM, yêu cầu 2-3 years", "unsuitable", None),
        ("Tuyển Java Intern tại HCM, được senior hướng dẫn", "suitable", "swe"),
        ("Java Developer HCM, ưu tiên có 1 năm kinh nghiệm", "review", "swe"),
        ("Java Intern HCM\nSenior Java Developer Hà Nội", "suitable", "swe"),
        ("Backend Intern Hà Nội\nMarketing Intern HCM", "unsuitable", None),
        ("Trụ sở HCM\nJava Developer làm việc tại Hà Nội, fresher", "unsuitable", None),
        ("Tuyển Java Intern\nĐịa điểm làm việc:\nTP.HCM", "suitable", "swe"),
        ("Khóa học Java Intern tại HCM", "unsuitable", None),
        ("Tuyển fresher HCM", "unsuitable", None),
        ("Không yêu cầu kinh nghiệm HCM", "unsuitable", None),
        ("Chấp nhận sinh viên mới ra trường HCM", "unsuitable", None),
    ],
)
def test_classify_target_profile(text, status, family):
    result = classify_job(text)
    assert result.status == status
    if family:
        assert family in result.matched_families or any(job.family == family for job in result.jobs)


def test_candidate_prefilter_does_not_match_internal():
    assert candidate_keyword_hits("Java Developer internal recruitment", ["intern", "developer"]) == ["developer"]


def test_result_serializes_evidence_without_normalizing_original_text():
    result = classify_job("Tuyển Java Backend Intern tại TP.HCM")
    payload = json.loads(result.to_json())
    assert payload["classifier_version"] == "job-profile-4"
    assert any("TP.HCM" in item["snippet"] for item in payload["jobs"][0]["evidence"])


@pytest.mark.parametrize("text,expected", [
    ("Hiring QA Intern HCM. Skills: Java, Selenium", "unsuitable"),
    ("Hiring Technical Support Intern HCM for industrial machinery", "unsuitable"),
    ("Java Developer HCM; Marketing Intern HCM", "review"),
    ("Java Developer Intern\nMarketing Intern HCM", "review"),
    ("Java Developer Intern HCM, minimum 12 months experience", "unsuitable"),
    ("Java Developer Intern HCM, 4 years experience", "unsuitable"),
    ("Java Developer HCM\nKhong nhan intern hoac fresher", "unsuitable"),
    ("Hiring Java Intern HCM mentored by senior engineers", "suitable"),
    ("Hiring Java Intern HCM\nBenefits: free English course", "suitable"),
    ("Hiring Java Intern HCM\nRequirements: preferred minimum 1 year experience", "suitable"),
])
def test_review_regressions(text, expected):
    assert classify_job(text).status == expected


@pytest.mark.parametrize("text", [
    "Data Analyst Intern HCM - Python, SQL",
    "Operations Intern HCM - dùng Python xử lý dữ liệu",
    "Content Intern HCM tại Java Coffee",
    "Product Intern HCM - làm việc với developer",
    "Tuyển sinh viên thực tập HCM, học Java miễn phí",
])
def test_non_swe_role_does_not_borrow_technology_or_developer_evidence(text):
    assert classify_job(text).status == "unsuitable"


@pytest.mark.parametrize("text", [
    "Data Analyst Intern HCM\nBackend Intern HCM",
    "Data Intern và Backend Intern HCM",
])
def test_post_is_suitable_when_a_separate_target_role_is_suitable(text):
    result = classify_job(text)
    assert result.status == "suitable"
    assert "swe" in result.matched_families


@pytest.mark.parametrize("text", [
    "Công ty trụ sở HCM - tuyển Java Intern làm việc tại Hà Nội",
    "Java Intern - làm việc tại Hà Nội hoặc HCM",
    "Java Intern HCM/Hà Nội",
    "Tuyển Java Intern, văn phòng HCM, địa điểm làm việc Hà Nội",
])
def test_conflicting_location_is_review(text):
    result = classify_job(text)
    assert result.status == "review"
    assert "location_unclear" in result.reason_codes


def test_family_selection_and_fingerprint():
    from monitor.core import Settings
    from monitor.job_matching import criteria_fingerprint

    swe = Settings(job_families=["swe"])
    helpdesk = Settings(job_families=["it_helpdesk_support"])
    assert classify_job("Java Developer Intern HCM", helpdesk).status == "unsuitable"
    assert classify_job("IT Support Fresher HCM", swe).status == "unsuitable"
    assert classify_job("IT Support Fresher HCM", helpdesk).status == "suitable"
    assert criteria_fingerprint(swe) != criteria_fingerprint(helpdesk)
