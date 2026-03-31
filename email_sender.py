from datetime import datetime
from email.message import EmailMessage
from email.utils import make_msgid
from html import escape
from pathlib import Path
import smtplib
import ssl
import re

from config import Settings
from course_parser import CourseTask
from models import NoticeItem


def append_email_diagnostic_log(output_dir: str, message: str) -> None:
    log_path = Path(output_dir) / "email_diagnostics.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] {message}\n")


def build_email_subject(
    target_source: str, now: datetime | None = None, slot: str = "noon"
) -> str:
    ts = now or datetime.now()
    if slot == "evening":
        return f"WHUT {target_source}晚间通知更新 {ts:%Y-%m-%d}"
    return f"WHUT {target_source}通知摘要 {ts:%Y-%m-%d}"


def build_backfill_subject(target_source: str, start_date: str, end_date: str) -> str:
    return f"WHUT {target_source}通知补发 {start_date} 至 {end_date}"


def build_course_task_email_subject(target_date: datetime, slot: str = "noon") -> str:
    if slot == "evening":
        return f"WHUT 课程任务提醒（晚间） {target_date:%Y-%m-%d}"
    return f"WHUT 课程任务提醒 {target_date:%Y-%m-%d}"


def build_course_task_email_body(tasks: list[CourseTask]) -> str:
    if not tasks:
        return "今日没有待完成任务"

    xiaoya_tasks = [t for t in tasks if t.source_platform == "xiaoya"]
    chaoxing_assignments = [
        t
        for t in tasks
        if t.source_platform == "chaoxing" and t.task_type == "assignment"
    ]
    chaoxing_exams = [
        t for t in tasks if t.source_platform == "chaoxing" and t.task_type == "exam"
    ]

    lines = ["今日课程待完成任务", ""]

    if xiaoya_tasks:
        lines.append("## 小雅课程任务")
        for task in xiaoya_tasks:
            lines.extend(
                [
                    f"课程：{task.course_name}",
                    f"任务：{task.title}",
                    f"截止：{task.deadline_text}",
                    "",
                ]
            )

    if chaoxing_assignments:
        lines.append("## 超星学习通 / 作业")
        for task in chaoxing_assignments:
            lines.extend(
                [
                    f"课程：{task.course_name}",
                    f"任务：{task.title}",
                    f"截止：{task.deadline_text}",
                    "",
                ]
            )

    if chaoxing_exams:
        lines.append("## 超星学习通 / 考试")
        for task in chaoxing_exams:
            lines.extend(
                [
                    f"课程：{task.course_name}",
                    f"任务：{task.title}",
                    f"截止：{task.deadline_text}",
                    "",
                ]
            )

    return "\n".join(lines).strip()


def build_course_task_email_html(tasks: list[CourseTask]) -> str:
    if not tasks:
        return (
            "<html><body><h1>课程任务提醒</h1><p>今日没有待完成任务</p></body></html>"
        )

    sections: list[str] = []

    xiaoya_tasks = [t for t in tasks if t.source_platform == "xiaoya"]
    chaoxing_assignments = [
        t
        for t in tasks
        if t.source_platform == "chaoxing" and t.task_type == "assignment"
    ]
    chaoxing_exams = [
        t for t in tasks if t.source_platform == "chaoxing" and t.task_type == "exam"
    ]

    if xiaoya_tasks:
        items = "".join(
            f"<li><strong>{escape(t.course_name)}</strong> - {escape(t.title)}<div>截止：{escape(t.deadline_text)}</div></li>"
            for t in xiaoya_tasks
        )
        sections.append(f"<h2>小雅课程任务</h2><ul>{items}</ul>")

    if chaoxing_assignments:
        items = "".join(
            f"<li><strong>{escape(t.course_name)}</strong> - {escape(t.title)}<div>截止：{escape(t.deadline_text)}</div></li>"
            for t in chaoxing_assignments
        )
        sections.append(f"<h2>超星学习通 / 作业</h2><ul>{items}</ul>")

    if chaoxing_exams:
        items = "".join(
            f"<li><strong>{escape(t.course_name)}</strong> - {escape(t.title)}<div>截止：{escape(t.deadline_text)}</div></li>"
            for t in chaoxing_exams
        )
        sections.append(f"<h2>超星学习通 / 考试</h2><ul>{items}</ul>")

    return f"<html><body><h1>课程任务提醒</h1>{''.join(sections)}</body></html>"


def build_email_body(
    summary: str, notices: list[NoticeItem], target_source: str
) -> str:
    lines = [
        f"{target_source}最近三天通知摘要",
        "",
        "AI 总结:",
        summary.strip(),
        "",
        "原始通知链接:",
    ]
    for item in notices:
        lines.append(f"- {item.title}: {item.url}")
    lines.extend(["", f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}"])
    return "\n".join(lines)


def _render_inline_markdown(text: str) -> str:
    escaped = escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def render_markdown_as_email_html(markdown: str) -> str:
    blocks: list[str] = []
    lines = markdown.strip().splitlines()
    paragraph_lines: list[str] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = " ".join(line.strip() for line in paragraph_lines)
        blocks.append(
            '<p style="margin:0 0 16px;color:#334155;line-height:1.8;">'
            f"{_render_inline_markdown(text)}</p>"
        )
        paragraph_lines.clear()

    def flush_list() -> None:
        if not list_items:
            return
        items = "".join(
            f"<li>{_render_inline_markdown(item)}</li>" for item in list_items
        )
        blocks.append(
            f'<ul style="margin:0 0 16px;padding-left:20px;color:#334155;">{items}</ul>'
        )
        list_items.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        if line == "---":
            flush_paragraph()
            flush_list()
            blocks.append(
                '<hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">'
            )
            continue
        if line.startswith("# "):
            flush_paragraph()
            flush_list()
            blocks.append(
                '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.4;color:#0f172a;">'
                f"{_render_inline_markdown(line[2:])}</h1>"
            )
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(
                '<h2 style="margin:0 0 14px;font-size:18px;line-height:1.5;color:#0f172a;">'
                f"{_render_inline_markdown(line[3:])}</h2>"
            )
            continue
        if line.startswith(("- ", "* ")):
            flush_paragraph()
            list_items.append(line[2:].strip())
            continue
        if line.startswith("> "):
            flush_paragraph()
            flush_list()
            blocks.append(
                '<blockquote style="margin:0 0 16px;padding:12px 16px;border-left:4px solid #99f6e4;'
                'background:#f0fdfa;color:#134e4a;">'
                f"{_render_inline_markdown(line[2:])}</blockquote>"
            )
            continue
        paragraph_lines.append(line)

    flush_paragraph()
    flush_list()
    return "".join(blocks)


def build_email_html(
    summary: str, notices: list[NoticeItem], target_source: str, slot: str = "noon"
) -> str:
    badge = "晚间更新" if slot == "evening" else "每日摘要"
    badge_background = "#fef3c7" if slot == "evening" else "#ccfbf1"
    badge_color = "#92400e" if slot == "evening" else "#115e59"
    summary_html = render_markdown_as_email_html(summary)
    notice_items = "".join(
        (
            '<li style="margin:0 0 12px;padding:14px 16px;border:1px solid #e2e8f0;'
            'border-radius:12px;background:#ffffff;list-style:none;">'
            f'<div style="font-weight:600;margin:0 0 4px;">{escape(item.title)}</div>'
            f'<div style="color:#64748b;font-size:13px;margin:0 0 8px;">{item.publish_time:%Y-%m-%d}</div>'
            f'<div><a href="{escape(item.url, quote=True)}" style="color:#0f766e;text-decoration:none;">'
            f"{escape(item.url)}</a></div>"
            "</li>"
        )
        for item in notices
    )
    if not notice_items:
        notice_items = (
            '<li style="margin:0;padding:14px 16px;border:1px solid #e2e8f0;'
            'border-radius:12px;background:#ffffff;list-style:none;">最近三天没有通知。</li>'
        )

    return (
        '<html><body style="margin:0;padding:24px;background:#f8fafc;color:#0f172a;">'
        '<div style="max-width:680px;margin:0 auto;line-height:1.7;">'
        '<div style="background:linear-gradient(135deg,#ffffff 0%,#f8fafc 100%);'
        'border:1px solid #e2e8f0;border-radius:20px;padding:24px;margin:0 0 16px;">'
        f'<div style="display:inline-block;padding:4px 10px;border-radius:999px;'
        f'background:{badge_background};color:{badge_color};font-size:12px;font-weight:700;">{badge}</div>'
        f'<h1 style="margin:16px 0 8px;font-size:24px;">WHUT {escape(target_source)}通知摘要</h1>'
        '<div style="margin:0;color:#475569;font-size:14px;">更易读的通知摘要与原始链接</div>'
        "</div>"
        '<div data-section="summary" style="background:#ffffff;border:1px solid #e2e8f0;'
        'border-radius:18px;padding:24px;margin:0 0 16px;">'
        '<div style="margin:0 0 14px;font-size:16px;font-weight:700;color:#0f172a;">摘要</div>'
        f"{summary_html}"
        "</div>"
        '<div data-section="notice-list" style="background:#f8fafc;border:1px solid #e2e8f0;'
        'border-radius:18px;padding:24px;">'
        '<div style="margin:0 0 14px;font-size:16px;font-weight:700;color:#0f172a;">原始通知链接</div>'
        f'<ul style="padding:0;margin:0 0 24px;">{notice_items}</ul>'
        f'<div style="color:#64748b;font-size:12px;">生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}</div>'
        "</div></body></html>"
    )


def build_backfill_html(
    target_source: str,
    start_date: str,
    end_date: str,
    date_sections: dict[str, str],
) -> str:
    sections = "".join(
        (
            '<section data-section="backfill-day" style="margin:0 0 16px;padding:20px;'
            'background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;">'
            f'<div style="margin:0 0 12px;font-size:16px;font-weight:700;color:#0f172a;">{escape(day)}</div>'
            f"{render_markdown_as_email_html(content)}"
            "</section>"
        )
        for day, content in sorted(date_sections.items())
    )
    return (
        '<html><body style="margin:0;padding:24px;background:#f8fafc;color:#0f172a;">'
        '<div style="max-width:720px;margin:0 auto;line-height:1.7;">'
        '<div style="background:linear-gradient(135deg,#ffffff 0%,#eff6ff 100%);'
        'border:1px solid #e2e8f0;border-radius:20px;padding:24px;margin:0 0 16px;">'
        '<div style="display:inline-block;padding:4px 10px;border-radius:999px;'
        'background:#dbeafe;color:#1d4ed8;font-size:12px;font-weight:700;">补发汇总</div>'
        f'<h1 style="margin:16px 0 8px;font-size:24px;">WHUT {escape(target_source)}通知补发</h1>'
        f'<div style="margin:0;color:#475569;font-size:14px;">{escape(start_date)} - {escape(end_date)}</div>'
        "</div>"
        f"{sections}"
        f'<div style="color:#64748b;font-size:12px;">生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}</div>'
        "</div></body></html>"
    )


def validate_email_settings(settings: Settings) -> None:
    missing = []
    if not settings.smtp_host:
        missing.append("SMTP_HOST")
    if not settings.smtp_port:
        missing.append("SMTP_PORT")
    if not settings.smtp_user:
        missing.append("SMTP_USER")
    if not settings.smtp_app_password:
        missing.append("SMTP_APP_PASSWORD")
    if not settings.email_to:
        missing.append("EMAIL_TO")
    if missing:
        raise ValueError("missing email settings: " + ", ".join(missing))


def send_email(
    settings: Settings, subject: str, body: str, html_body: str | None = None
) -> None:
    validate_email_settings(settings)

    msg = EmailMessage()
    msg["From"] = settings.smtp_user
    msg["To"] = settings.email_to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=settings.smtp_host)
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    message_id = msg["Message-ID"]
    append_email_diagnostic_log(
        settings.output_dir,
        (
            f"send_email:start subject={subject!r} to={settings.email_to!r} "
            f"message_id={message_id!r} html={'yes' if html_body else 'no'}"
        ),
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(settings.smtp_user, settings.smtp_app_password)
        smtp.send_message(msg)

    append_email_diagnostic_log(
        settings.output_dir,
        f"send_email:done subject={subject!r} message_id={message_id!r}",
    )
    print(f"[EMAIL_TRACE] subject={subject} | message_id={message_id}")
