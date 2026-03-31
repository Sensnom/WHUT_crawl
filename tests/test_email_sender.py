from datetime import datetime

import pytest
import ssl

from config import Settings
from models import NoticeItem


def test_build_email_body_contains_summary_and_links():
    from email_sender import build_email_body

    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 18, 8, 0),
            source="本科生院",
        )
    ]
    body = build_email_body("- 要点1", notices, "本科生院")
    assert "要点1" in body
    assert "原始通知链接" in body
    assert "http://example.com/a" in body


def test_build_course_task_email_body_includes_tasks_and_deadlines():
    from course_parser import CourseTask
    from email_sender import build_course_task_email_body

    tasks = [
        CourseTask(
            title="作业 3",
            course_name="高等数学",
            deadline_text="2026-03-21 23:59",
        )
    ]

    body = build_course_task_email_body(tasks)

    assert "高等数学" in body
    assert "作业 3" in body
    assert "2026-03-21 23:59" in body


def test_build_course_task_email_body_uses_empty_state_message():
    from email_sender import build_course_task_email_body

    body = build_course_task_email_body([])

    assert "今日没有待完成任务" in body


def test_render_markdown_as_email_html_formats_lists_and_paragraphs():
    from email_sender import render_markdown_as_email_html

    html = render_markdown_as_email_html("- 要点一\n- 要点二\n\n结论段落")

    assert "<ul" in html
    assert "<li>要点一</li>" in html
    assert "<li>要点二</li>" in html
    assert "<p" in html
    assert "结论段落" in html


def test_render_markdown_as_email_html_supports_headings_bold_quotes_and_dividers():
    from email_sender import render_markdown_as_email_html

    html = render_markdown_as_email_html(
        "# 标题\n\n## 小节\n\n**重点**\n\n> 引用\n\n---"
    )

    assert "<h1" in html
    assert "标题" in html
    assert "<h2" in html
    assert "<strong>重点</strong>" in html
    assert "<blockquote" in html
    assert "引用" in html
    assert '<hr style="' in html


def test_render_markdown_as_email_html_escapes_raw_html_input():
    from email_sender import render_markdown_as_email_html

    html = render_markdown_as_email_html("<script>alert('x')</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_build_email_html_contains_summary_and_notice_links():
    from email_sender import build_email_html

    notice = NoticeItem(
        title="通知A",
        url="http://example.com/a",
        publish_time=datetime(2026, 3, 18, 8, 0),
        source="本科生院",
    )

    html = build_email_html("- 要点一", [notice], "本科生院")

    assert "<html" in html.lower()
    assert "每日摘要" in html
    assert 'data-section="summary"' in html
    assert 'data-section="notice-list"' in html
    assert "<ul" in html
    assert "<li>要点一</li>" in html
    assert notice.url in html


def test_build_email_html_marks_evening_variant():
    from email_sender import build_email_html

    html = build_email_html("- 晚间要点", [], "本科生院", slot="evening")

    assert "晚间更新" in html


def test_build_backfill_html_contains_date_range_and_sections():
    from email_sender import build_backfill_html

    html = build_backfill_html(
        "本科生院",
        "2026-03-17",
        "2026-03-18",
        {
            "2026-03-17": "# 2026-03-17\n- 内容A",
            "2026-03-18": "# 2026-03-18\n- 内容B",
        },
    )

    assert "补发汇总" in html
    assert "2026-03-17" in html
    assert "2026-03-18" in html
    assert "内容A" in html
    assert "内容B" in html
    assert "<pre" not in html
    assert 'data-section="backfill-day"' in html


def test_send_email_uses_tls_and_login(monkeypatch):
    from email_sender import send_email

    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self, context=None):
            calls.append(("starttls", context))

        def ehlo(self):
            calls.append("ehlo")
            return (250, b"ok")

        def login(self, user, password):
            calls.append(("login", user, password))

        def send_message(self, msg):
            calls.append(("send_message", msg["To"], msg["Subject"]))

    monkeypatch.setattr("email_sender.smtplib.SMTP", FakeSMTP)

    settings = Settings(
        api_key="k",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        request_timeout=60,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="y2902341094@gmail.com",
        smtp_app_password="app-pass",
        email_to="y2902341094@gmail.com",
    )
    send_email(settings, "subject", "body", "<html><body>body</body></html>")

    assert calls[1] == "ehlo"
    assert calls[2][0] == "starttls"
    assert isinstance(calls[2][1], ssl.SSLContext)
    assert calls[3] == "ehlo"
    assert calls[4] == ("login", "y2902341094@gmail.com", "app-pass")
    assert calls[5] == ("send_message", "y2902341094@gmail.com", "subject")


def test_send_email_builds_multipart_message_with_html(monkeypatch):
    from email_sender import send_email

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self, context=None):
            return None

        def ehlo(self):
            return (250, b"ok")

        def login(self, user, password):
            return None

        def send_message(self, msg):
            sent["message"] = msg

    monkeypatch.setattr("email_sender.smtplib.SMTP", FakeSMTP)

    settings = Settings(
        api_key="k",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        request_timeout=60,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="y2902341094@gmail.com",
        smtp_app_password="app-pass",
        email_to="y2902341094@gmail.com",
    )

    send_email(settings, "subject", "plain body", "<html><body>html body</body></html>")

    msg = sent["message"]
    assert msg.is_multipart() is True
    assert msg.get_content_type() == "multipart/alternative"
    payload = msg.get_payload()
    assert len(payload) == 2
    assert payload[0].get_content_type() == "text/plain"
    assert payload[1].get_content_type() == "text/html"


def test_send_email_requires_smtp_settings():
    from email_sender import send_email

    settings = Settings(
        api_key="k",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        request_timeout=60,
    )

    with pytest.raises(ValueError):
        send_email(settings, "subject", "body", "<html><body>body</body></html>")


def test_build_backfill_subject_formats_date_range():
    from email_sender import build_backfill_subject

    subject = build_backfill_subject("本科生院", "2026-03-12", "2026-03-18")

    assert subject == "WHUT 本科生院通知补发 2026-03-12 至 2026-03-18"


def test_build_course_task_email_body_groups_tasks_by_platform_and_type():
    from course_parser import CourseTask
    from email_sender import build_course_task_email_body

    tasks = [
        CourseTask(
            title="小雅作业",
            course_name="高数",
            deadline_text="2026-03-25 23:59",
            source_platform="xiaoya",
            task_type="task",
        ),
        CourseTask(
            title="超星作业",
            course_name="大物",
            deadline_text="2026-03-26 23:59",
            source_platform="chaoxing",
            task_type="assignment",
        ),
        CourseTask(
            title="超星考试",
            course_name="大物",
            deadline_text="2026-03-27 23:59",
            source_platform="chaoxing",
            task_type="exam",
        ),
    ]

    body = build_course_task_email_body(tasks)

    assert "小雅课程任务" in body
    assert "超星学习通 / 作业" in body
    assert "超星学习通 / 考试" in body
    assert "小雅作业" in body
    assert "超星作业" in body
    assert "超星考试" in body
