import smtplib
from datetime import datetime
from pathlib import Path

from config import Settings
from course_client import CourseClient
from course_parser import CourseTask, parse_pending_course_tasks
from delivery_state import DeliveryStateStore
from typing import Callable

try:
    from chaoxing_client import ChaoxingClient
except ImportError:
    ChaoxingClient = None

try:
    from mooc_client import MoocClient
except ImportError:
    MoocClient = None


def fetch_course_tasks(
    settings: Settings,
    *,
    course_client_factory: Callable[[Settings], CourseClient] = CourseClient,
    chaoxing_client_factory: Callable[[Settings], "ChaoxingClient"] | None = None,
    mooc_client_factory: Callable[[Settings], "MoocClient"] | None = None,
) -> tuple[list[CourseTask], list[str]]:
    warnings: list[str] = []
    all_tasks: list[CourseTask] = []

    xiaoya_tasks, xiaoya_warning = _fetch_xiaoya_tasks(settings, course_client_factory)
    all_tasks.extend(xiaoya_tasks)
    if xiaoya_warning:
        warnings.append(xiaoya_warning)

    if chaoxing_client_factory is not None and ChaoxingClient is not None:
        chaoxing_tasks, chaoxing_warnings = _fetch_chaoxing_tasks(
            settings, chaoxing_client_factory
        )
        all_tasks.extend(chaoxing_tasks)
        warnings.extend(chaoxing_warnings)

    if mooc_client_factory is not None and MoocClient is not None:
        mooc_tasks, mooc_warnings = _fetch_mooc_tasks(settings, mooc_client_factory)
        all_tasks.extend(mooc_tasks)
        warnings.extend(mooc_warnings)

    all_tasks.sort(key=lambda t: t.deadline_at or datetime.max)
    return all_tasks, warnings


def _fetch_xiaoya_tasks(
    settings: Settings,
    course_client_factory: Callable[[Settings], CourseClient],
) -> tuple[list[CourseTask], str]:
    if not settings.smart_whut_username or not settings.smart_whut_password:
        return [], ""

    try:
        client = course_client_factory(settings)
        html = client.fetch_course_page_html()
        return parse_pending_course_tasks(html), ""
    except Exception as exc:
        return [], f"小雅课程任务爬取失败: {exc}"


def _fetch_chaoxing_tasks(
    settings: Settings,
    chaoxing_client_factory: Callable[[Settings], "ChaoxingClient"],
) -> tuple[list[CourseTask], list[str]]:
    if (
        not settings.enable_chaoxing_service
        or not settings.chaoxing_username
        or not settings.chaoxing_password
        or not settings.chaoxing_target_course_names
    ):
        return [], []

    try:
        client = chaoxing_client_factory(settings)
        return client.fetch_pending_tasks()
    except Exception as exc:
        return [], [f"超星学习通任务爬取失败: {exc}"]


def _fetch_mooc_tasks(
    settings: Settings,
    mooc_client_factory: Callable[[Settings], "MoocClient"],
) -> tuple[list[CourseTask], list[str]]:
    if (
        not settings.enable_mooc_service
        or not settings.mooc_email
        or not settings.mooc_password
    ):
        return [], []

    try:
        client = mooc_client_factory(settings)
        return client.fetch_pending_tasks()
    except Exception as exc:
        return [], [f"MOOC课程任务爬取失败: {exc}"]


def send_course_task_email(
    settings: Settings,
    target_date: datetime,
    slot: str,
    *,
    fetch_course_tasks_fn: Callable[[Settings], list[CourseTask]],
    build_course_task_email_subject_fn: Callable[[datetime, str], str],
    build_course_task_email_body_fn: Callable[[list[CourseTask]], str],
    build_course_task_email_html_fn: Callable[[list[CourseTask]], str],
    send_email_fn: Callable[[Settings, str, str, str], None],
) -> tuple[str, str, str]:
    tasks = fetch_course_tasks_fn(settings)
    subject = build_course_task_email_subject_fn(target_date, slot)
    body = build_course_task_email_body_fn(tasks)
    html = build_course_task_email_html_fn(tasks)
    send_email_fn(settings, subject, body, html)
    return subject, body, html


def get_course_task_artifact_path(
    output_dir: str, target_date: datetime, slot: str
) -> Path:
    return Path(output_dir) / f"course_tasks_{target_date:%Y%m%d}_{slot}.md"


def write_course_task_artifact(
    output_dir: str,
    subject: str,
    body: str,
    html: str,
    target_date: datetime,
    slot: str,
) -> Path:
    artifact_path = get_course_task_artifact_path(output_dir, target_date, slot)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        f"# {subject}\n\n## Plain Text\n\n{body.strip()}\n\n## HTML\n\n{html.strip()}\n",
        encoding="utf-8",
    )
    return artifact_path


def process_course_task_delivery(
    settings: Settings,
    store: DeliveryStateStore,
    target_date: datetime,
    slot: str,
    *,
    get_course_task_slot_fn: Callable[[str], str],
    get_course_task_artifact_path_fn: Callable[[str, datetime, str], Path],
    send_course_task_email_fn: Callable[
        [Settings, datetime, str], tuple[str, str, str]
    ],
    write_course_task_artifact_fn: Callable[[str, str, str, str, datetime, str], Path],
    save_delivery_record_fn: Callable[..., None],
    print_fn: Callable[[str], None] = print,
) -> None:
    course_slot = get_course_task_slot_fn(slot)
    artifact_path = get_course_task_artifact_path_fn(
        settings.output_dir, target_date, slot
    )
    existing = store.get_record(target_date.date().isoformat(), course_slot)
    print_fn(
        f"[COURSE_TRACE] enter slot={slot} course_slot={course_slot} target_date={target_date.date().isoformat()} existing={existing!r}"
    )

    try:
        subject, body, html = send_course_task_email_fn(settings, target_date, slot)
        print_fn(
            f"[COURSE_TRACE] send subject={subject!r} artifact={str(artifact_path)!r}"
        )
        artifact_path = write_course_task_artifact_fn(
            settings.output_dir,
            subject,
            body,
            html,
            target_date,
            slot,
        )
        save_delivery_record_fn(
            store,
            target_date,
            course_slot,
            artifact_path,
            [],
            True,
            "sent",
        )
    except (ValueError, RuntimeError, smtplib.SMTPException, OSError) as exc:
        print_fn(f"[WARN] 课程任务邮件发送失败: {exc}")
        save_delivery_record_fn(
            store,
            target_date,
            course_slot,
            artifact_path,
            [],
            False,
            "failed",
            warning_emitted=True,
        )
