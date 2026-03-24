from datetime import datetime
from pathlib import Path

from config import Settings
from course_parser import CourseTask
from delivery_state import DeliveryRecord, DeliveryStateStore
from services.course_service import (
    fetch_course_tasks,
    process_course_task_delivery,
    send_course_task_email,
)


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        api_key="k",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        request_timeout=60,
        output_dir=str(tmp_path),
        target_source="本科生院",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_app_password="app-pass",
        email_to="receiver@example.com",
        schedule_hour=12,
        schedule_minute=0,
        evening_schedule_hour=18,
        evening_schedule_minute=0,
        backfill_max_days=2,
        state_retention_days=15,
    )


def test_fetch_course_tasks_skips_client_without_credentials(tmp_path: Path):
    settings = make_settings(tmp_path)

    def unexpected_factory(_settings: Settings):
        raise AssertionError("client should not be created without credentials")

    assert fetch_course_tasks(settings, course_client_factory=unexpected_factory) == []


def test_send_course_task_email_builds_and_sends_expected_content(tmp_path: Path):
    settings = make_settings(tmp_path)
    tasks = [
        CourseTask(
            title="作业 3",
            course_name="高等数学",
            deadline_text="2026-03-21 23:59",
        )
    ]
    sent: list[tuple[str, str, str]] = []

    subject, body, html = send_course_task_email(
        settings,
        datetime(2026, 3, 20, 12, 0),
        "noon",
        fetch_course_tasks_fn=lambda _settings: tasks,
        build_course_task_email_subject_fn=lambda target_date, slot: (
            f"subject-{target_date.date().isoformat()}-{slot}"
        ),
        build_course_task_email_body_fn=lambda items: f"body-{items[0].title}",
        build_course_task_email_html_fn=lambda items: f"<p>{items[0].course_name}</p>",
        send_email_fn=lambda _settings, sent_subject, sent_body, sent_html: sent.append(
            (sent_subject, sent_body, sent_html)
        ),
    )

    assert (subject, body, html) == (
        "subject-2026-03-20-noon",
        "body-作业 3",
        "<p>高等数学</p>",
    )
    assert sent == [(subject, body, html)]


def test_process_course_task_delivery_writes_and_records_course_artifact(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    saved: dict[str, object] = {}
    written: list[tuple[str, str, str, datetime, str]] = []

    def send_course_task_email_fn(
        _settings: Settings, target_date: datetime, slot: str
    ):
        assert target_date == datetime(2026, 3, 20, 0, 0)
        assert slot == "noon"
        return ("课程提醒", "正文", "<p>正文</p>")

    def write_course_task_artifact_fn(
        output_dir: str,
        subject: str,
        body: str,
        html: str,
        target_date: datetime,
        slot: str,
    ) -> Path:
        written.append((output_dir, subject, body, target_date, slot))
        artifact_path = tmp_path / "course_tasks_20260320_noon.md"
        artifact_path.write_text(f"# {subject}\n\n{body}\n\n{html}\n", encoding="utf-8")
        return artifact_path

    def save_delivery_record(*args, **kwargs):
        saved["args"] = args
        saved["kwargs"] = kwargs

    process_course_task_delivery(
        settings,
        store,
        datetime(2026, 3, 20, 0, 0),
        "noon",
        get_course_task_slot_fn=lambda slot: f"course_tasks_{slot}",
        get_course_task_artifact_path_fn=lambda output_dir, target_date, slot: (
            Path(output_dir) / f"course_tasks_{target_date:%Y%m%d}_{slot}.md"
        ),
        send_course_task_email_fn=send_course_task_email_fn,
        write_course_task_artifact_fn=write_course_task_artifact_fn,
        save_delivery_record_fn=save_delivery_record,
    )

    assert written == [
        (
            str(tmp_path),
            "课程提醒",
            "正文",
            datetime(2026, 3, 20, 0, 0),
            "noon",
        )
    ]
    assert saved["args"] == (
        store,
        datetime(2026, 3, 20, 0, 0),
        "course_tasks_noon",
        tmp_path / "course_tasks_20260320_noon.md",
        [],
        True,
        "sent",
    )
    assert saved["kwargs"] == {}
    assert (tmp_path / "course_tasks_20260320_noon.md").exists()


def test_process_course_task_delivery_sends_again_even_when_today_already_succeeded(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="course_tasks_noon",
            summary_path=str(tmp_path / "course_tasks_20260320_noon.md"),
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )
    send_calls = {"count": 0}

    process_course_task_delivery(
        settings,
        store,
        datetime(2026, 3, 20, 0, 0),
        "noon",
        get_course_task_slot_fn=lambda slot: f"course_tasks_{slot}",
        get_course_task_artifact_path_fn=lambda output_dir, target_date, slot: (
            Path(output_dir) / f"course_tasks_{target_date:%Y%m%d}_{slot}.md"
        ),
        send_course_task_email_fn=lambda *_args: (
            send_calls.__setitem__("count", send_calls["count"] + 1)
            or ("课程提醒", "正文", "<p>正文</p>")
        ),
        write_course_task_artifact_fn=lambda output_dir, *_args: (
            Path(output_dir) / "course_tasks_20260320_noon.md"
        ),
        save_delivery_record_fn=lambda *_args, **_kwargs: None,
    )

    assert send_calls["count"] == 1


def test_process_course_task_delivery_updates_record_after_repeat_same_day_send(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="course_tasks_noon",
            summary_path=str(tmp_path / "course_tasks_20260320_noon.md"),
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )
    latest_artifact_path = tmp_path / "course_tasks_20260320_noon_repeat.md"
    send_calls = {"count": 0}

    def save_delivery_record_fn(
        state_store: DeliveryStateStore,
        target_date: datetime,
        course_slot: str,
        artifact_path: Path,
        notice_urls: list[str],
        email_sent: bool,
        status: str,
        warning_emitted: bool = False,
    ) -> None:
        state_store.record(
            DeliveryRecord(
                date=target_date.date().isoformat(),
                slot=course_slot,
                summary_path=str(artifact_path),
                email_sent=email_sent,
                notice_urls=notice_urls,
                status=status,
                warning_emitted=warning_emitted,
            )
        )

    process_course_task_delivery(
        settings,
        store,
        datetime(2026, 3, 20, 0, 0),
        "noon",
        get_course_task_slot_fn=lambda slot: f"course_tasks_{slot}",
        get_course_task_artifact_path_fn=lambda output_dir, target_date, slot: (
            Path(output_dir) / f"course_tasks_{target_date:%Y%m%d}_{slot}.md"
        ),
        send_course_task_email_fn=lambda *_args: (
            send_calls.__setitem__("count", send_calls["count"] + 1)
            or ("课程提醒", "更新后的正文", "<p>更新后的正文</p>")
        ),
        write_course_task_artifact_fn=lambda *_args: latest_artifact_path,
        save_delivery_record_fn=save_delivery_record_fn,
    )

    record = store.get_record("2026-03-20", "course_tasks_noon")

    assert send_calls["count"] == 1
    assert record is not None
    assert record["summary_path"] == str(latest_artifact_path)
    assert record["email_sent"] is True
    assert record["status"] == "sent"
