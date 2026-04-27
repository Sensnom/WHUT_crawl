from argparse import Namespace
from datetime import datetime
from pathlib import Path
import smtplib
from typing import Any
from zoneinfo import ZoneInfo

from delivery_state import DeliveryRecord, DeliveryStateStore, get_state_path
from main import (
    build_napcat_news_message,
    enrich_notice_content,
    fetch_course_tasks,
    format_summary_markdown,
    get_current_delivery_slot,
    get_summary_file_path_for_date,
    get_target_delivery_date,
    load_settings_for_mode,
    main,
    process_evening_delivery,
    process_course_task_delivery,
    save_delivery_record,
    run,
    run_news_mode,
    write_summary_file,
)
from models import NoticeItem


def make_settings(tmp_path: Path):
    from config import Settings

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
        backfill_max_days=1,
        state_retention_days=15,
    )


def test_write_summary_file_creates_markdown(tmp_path: Path):
    output = write_summary_file("hello", output_dir=str(tmp_path))
    assert output.exists()
    assert output.suffix == ".md"
    assert output.read_text(encoding="utf-8") == "hello"


def test_get_summary_file_path_for_date(tmp_path: Path):
    path = get_summary_file_path_for_date(str(tmp_path), datetime(2026, 3, 18, 8, 0))
    assert path == tmp_path / "summary_20260318.md"


def test_get_summary_file_path_for_evening_slot(tmp_path: Path):
    path = get_summary_file_path_for_date(
        str(tmp_path), datetime(2026, 3, 18, 18, 0), slot="evening"
    )
    assert path == tmp_path / "summary_20260318_evening.md"


def test_get_target_delivery_date_before_noon_uses_previous_day():
    result = get_target_delivery_date(datetime(2026, 3, 19, 11, 0), 12)
    assert result.date().isoformat() == "2026-03-18"


def test_get_target_delivery_date_at_noon_uses_today():
    result = get_target_delivery_date(datetime(2026, 3, 19, 12, 0), 12)
    assert result.date().isoformat() == "2026-03-19"


def test_get_target_delivery_date_respects_schedule_minute():
    before = get_target_delivery_date(datetime(2026, 3, 19, 12, 29), 12, 30)
    after = get_target_delivery_date(datetime(2026, 3, 19, 12, 30), 12, 30)
    assert before.date().isoformat() == "2026-03-18"
    assert after.date().isoformat() == "2026-03-19"


def test_get_current_delivery_slot_returns_expected_values():
    assert get_current_delivery_slot(datetime(2026, 3, 19, 11, 0), 12, 0, 18, 0) is None
    assert (
        get_current_delivery_slot(datetime(2026, 3, 19, 12, 0), 12, 0, 18, 0) == "noon"
    )
    assert (
        get_current_delivery_slot(datetime(2026, 3, 19, 18, 0), 12, 0, 18, 0)
        == "evening"
    )
    assert get_current_delivery_slot(datetime(2026, 3, 19, 19, 0), 12, 0, 18, 0) is None


def test_format_summary_markdown_adds_heading_and_notice_list():
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 18, 9, 0),
            source="本科生院",
            content="正文",
        )
    ]
    result = format_summary_markdown("- 要点1", notices, "本科生院")
    assert result.startswith("# 本科生院最近三天通知总结")
    assert "## 涉及通知" in result
    assert "通知A" in result


def test_build_napcat_news_message_uses_lightweight_layout():
    notices = [
        NoticeItem(
            title="关于组织测试活动的通知",
            url="http://i.whut.edu.cn/test",
            publish_time=datetime(2026, 4, 27, 18, 0),
            source="本科生院",
        )
    ]
    markdown = "# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **测试事项**：今晚提交。\n"

    message = build_napcat_news_message(markdown, notices)

    assert message.startswith("本科生院最近三天通知总结")
    assert "\n\n摘要\n" in message
    assert "涉及通知" in message
    assert "[" not in message
    assert "#" not in message
    assert "http://i.whut.edu.cn/test" in message


def test_build_napcat_news_message_uses_default_summary_when_body_missing():
    message = build_napcat_news_message(
        "# 本科生院最近三天通知总结\n\n## 摘要\n",
        [],
    )

    assert "摘要\n最近三天没有通知。" in message
    assert "涉及通知" not in message


def test_build_napcat_news_message_accepts_non_standard_summary_heading():
    notices = [
        NoticeItem(
            title="关于组织测试活动的通知",
            url="http://i.whut.edu.cn/test",
            publish_time=datetime(2026, 4, 27, 18, 0),
            source="本科生院",
        )
    ]
    markdown = "# 本科生院最近三天通知总结\n\n### 摘要\n\n1. **测试事项**：今晚提交。\n\n### 其他\n忽略\n"

    message = build_napcat_news_message(markdown, notices)

    assert "摘要\n1. 测试事项：今晚提交。" in message
    assert "忽略" not in message


def test_build_napcat_news_message_uses_notice_links_from_markdown_when_notices_missing():
    markdown = (
        "# 本科生院最近三天通知总结\n\n"
        "## 摘要\n\n"
        "1. **测试事项**：今晚提交。\n\n"
        "## 涉及通知\n\n"
        "- `2026-04-27` [关于组织测试活动的通知](http://i.whut.edu.cn/test)\n"
    )

    message = build_napcat_news_message(markdown, [])

    assert "涉及通知\n1. 关于组织测试活动的通知\nhttp://i.whut.edu.cn/test" in message


def test_enrich_notice_content_keeps_notice_when_detail_fetch_fails(monkeypatch):
    def fake_fetch_html(url: str, timeout: int = 20, retries: int = 2) -> str:
        raise RuntimeError("network error")

    monkeypatch.setattr("main.fetch_html", fake_fetch_html)

    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 18, 9, 0),
            source="本科生院",
        )
    ]
    result = enrich_notice_content(notices, timeout=10)
    assert len(result) == 1
    assert result[0].content == ""


def test_fetch_course_tasks_parses_rendered_html_from_course_client(monkeypatch):
    class FakeCourseClient:
        def __init__(self, settings):
            self.settings = settings

        def fetch_course_page_html(self):
            return """
            <div class="task-item">
              <div class="course-name">高等数学</div>
              <div class="task-title">作业 3</div>
              <div class="deadline">截止时间：2026-03-21 23:59</div>
            </div>
            """

    settings = make_settings(Path("."))
    settings.smart_whut_username = "2020123456"
    settings.smart_whut_password = "secret"
    monkeypatch.setattr("main.CourseClient", FakeCourseClient)

    tasks = fetch_course_tasks(settings)

    assert len(tasks) == 1
    assert tasks[0].title == "作业 3"


def test_run_dispatches_explicit_news_mode(monkeypatch):
    called = []

    monkeypatch.setattr("main.parse_args", lambda: Namespace(mode="news"))
    monkeypatch.setattr(
        "main.run_news_mode", lambda runtime: called.append("news") or 0
    )

    assert main() == 0
    assert called == ["news"]


def test_default_main_mode_still_runs_daily_workflow(monkeypatch):
    called = []

    monkeypatch.setattr("main.parse_args", lambda: Namespace(mode="run"))
    monkeypatch.setattr(
        "main.run_daily_workflow", lambda runtime: called.append("run") or 0
    )

    assert main() == 0
    assert called == ["run"]


def test_main_validates_run_mode_before_building_runtime(monkeypatch):
    validated_settings: object = object()
    runtime: object = object()
    events: list[tuple[str, object]] = []

    monkeypatch.setattr("main.parse_args", lambda: Namespace(mode="run"))
    monkeypatch.setattr(
        "main.load_settings_for_mode",
        lambda mode: events.append(("validate", mode)) or validated_settings,
    )

    def fake_build_runtime(*, settings_loader):
        events.append(("build", settings_loader()))
        return runtime

    monkeypatch.setattr("main.build_runtime", fake_build_runtime)
    monkeypatch.setattr(
        "main.run_daily_workflow",
        lambda received_runtime: events.append(("dispatch", received_runtime)) or 0,
    )

    assert main() == 0
    assert events == [
        ("validate", "run"),
        ("build", validated_settings),
        ("dispatch", runtime),
    ]


def test_main_dispatches_healthcheck_without_building_runtime(monkeypatch):
    settings = make_settings(Path("."))
    settings.smtp_user = ""
    settings.smtp_app_password = ""
    settings.email_to = ""

    monkeypatch.setattr("main.parse_args", lambda: Namespace(mode="healthcheck"))
    monkeypatch.setattr(
        "main.build_runtime",
        lambda: (_ for _ in ()).throw(AssertionError("should not build runtime")),
    )
    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.run_healthcheck",
        lambda received_settings: 17 if received_settings is settings else -1,
        raising=False,
    )

    assert main() == 17


def test_load_settings_for_healthcheck_does_not_require_api_key(monkeypatch, tmp_path):
    monkeypatch.setattr("config.PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("MAX_PAGES", "3")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SCHEDULE_HOUR", "12")
    monkeypatch.setenv("SCHEDULE_MINUTE", "0")
    monkeypatch.setenv("EVENING_SCHEDULE_HOUR", "18")
    monkeypatch.setenv("EVENING_SCHEDULE_MINUTE", "0")
    monkeypatch.setenv("BACKFILL_MAX_DAYS", "7")
    monkeypatch.setenv("STATE_RETENTION_DAYS", "15")

    settings = load_settings_for_mode("healthcheck")

    assert settings.api_key == ""


def test_save_delivery_record_persists_successful_napcat_metadata(tmp_path: Path):
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)

    save_delivery_record(
        store,
        datetime(2026, 3, 20, 0, 0),
        "evening",
        tmp_path / "summary_20260320_evening.md",
        ["https://example.com/new"],
        True,
        "sent",
        now=now,
        napcat_sent=True,
        napcat_target_results=[{"target": "group:123", "sent": True, "error": ""}],
    )

    record = store.get_record("2026-03-20", "evening")

    assert record is not None
    assert record["email_sent"] is True
    assert record["napcat_sent"] is True
    assert record["napcat_error"] == ""
    assert record["napcat_target_results"] == [
        {"target": "group:123", "sent": True, "error": ""}
    ]
    assert record["sent_at"] == now.isoformat()
    assert record["updated_at"] == now.isoformat()


def test_save_delivery_record_persists_failed_napcat_metadata(tmp_path: Path):
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 5)

    save_delivery_record(
        store,
        datetime(2026, 3, 20, 0, 0),
        "evening",
        tmp_path / "summary_20260320_evening.md",
        ["https://example.com/new"],
        False,
        "failed",
        warning_emitted=True,
        now=now,
        napcat_sent=False,
        napcat_error="timeout",
        napcat_target_results=[{"target": "group:123", "sent": False, "error": "timeout"}],
    )

    record = store.get_record("2026-03-20", "evening")

    assert record is not None
    assert record["email_sent"] is False
    assert record["napcat_sent"] is False
    assert record["napcat_error"] == "timeout"
    assert record["napcat_target_results"] == [
        {"target": "group:123", "sent": False, "error": "timeout"}
    ]
    assert record["warning_emitted"] is True
    assert record["sent_at"] == ""
    assert record["updated_at"] == now.isoformat()


def test_save_delivery_record_preserves_existing_napcat_metadata_when_omitted(
    tmp_path: Path,
):
    store = DeliveryStateStore(tmp_path / "state.json")

    save_delivery_record(
        store,
        datetime(2026, 3, 20, 0, 0),
        "evening",
        tmp_path / "summary_20260320_evening.md",
        ["https://example.com/new"],
        True,
        "sent",
        now=datetime(2026, 3, 20, 18, 0),
        napcat_sent=True,
        napcat_error="",
        napcat_target_results=[
            {"target": "group:123", "sent": True, "error": ""}
        ],
    )

    save_delivery_record(
        store,
        datetime(2026, 3, 20, 0, 0),
        "evening",
        tmp_path / "summary_20260320_evening.md",
        ["https://example.com/new"],
        False,
        "failed",
        warning_emitted=True,
        now=datetime(2026, 3, 20, 18, 5),
    )

    record = store.get_record("2026-03-20", "evening")

    assert record is not None
    assert record["napcat_sent"] is True
    assert record["napcat_error"] == ""
    assert record["napcat_target_results"] == [
        {"target": "group:123", "sent": True, "error": ""}
    ]
    assert record["sent_at"] == "2026-03-20T18:00:00"
    assert record["updated_at"] == "2026-03-20T18:05:00"


def test_process_evening_delivery_wires_napcat_dependencies(monkeypatch, tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    captured: dict[str, object] = {}

    def fake_process_evening_delivery_service(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return 9

    monkeypatch.setattr(
        "main.process_evening_delivery_service", fake_process_evening_delivery_service
    )

    assert process_evening_delivery(settings, store, now) == 9
    assert captured["args"] == (settings, store, now)
    assert captured["kwargs"]["send_napcat_message_fn"] is __import__(
        "main"
    ).send_napcat_message
    assert captured["kwargs"]["build_napcat_news_message_fn"] is build_napcat_news_message


def test_run_news_mode_uses_injected_runtime(monkeypatch):
    runtime: Any = object()

    monkeypatch.setattr(
        "main.build_runtime",
        lambda: (_ for _ in ()).throw(AssertionError("should not rebuild runtime")),
    )
    monkeypatch.setattr(
        "main.run_daily_workflow",
        lambda received_runtime: 7 if received_runtime is runtime else -1,
    )

    assert run_news_mode(runtime) == 7


def test_run_mode_calls_news_and_course_services_independently(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(
        "main.load_settings_for_mode", lambda mode: make_settings(tmp_path)
    )
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.cleanup_old_delivery_data", lambda _settings, _store, _now: None
    )
    monkeypatch.setattr(
        "main.retry_failed_deliveries_for_today",
        lambda _settings, _store, _now: set(),
    )
    monkeypatch.setattr(
        "main.send_backfill_if_needed",
        lambda _settings, _store, _now, _include_today: None,
    )
    monkeypatch.setattr(
        "main.process_news_run",
        lambda received_runtime: calls.append(("news", received_runtime)),
    )
    monkeypatch.setattr(
        "main.process_course_run",
        lambda received_runtime: calls.append(("course", received_runtime)),
    )

    assert run() == 0
    assert [name for name, _runtime in calls[:2]] == ["course", "news"]
    assert len({id(received_runtime) for _name, received_runtime in calls[:2]}) == 1


def test_run_skips_all_news_steps_when_news_service_is_disabled(monkeypatch, tmp_path):
    calls = []
    settings = make_settings(tmp_path)
    settings.enable_news_service = False

    monkeypatch.setattr("main.load_settings_for_mode", lambda mode: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.cleanup_old_delivery_data", lambda _settings, _store, _now: None
    )
    monkeypatch.setattr(
        "main.retry_failed_deliveries_for_today",
        lambda *_args: calls.append("retry") or set(),
    )
    monkeypatch.setattr(
        "main.send_backfill_if_needed", lambda *_args: calls.append("backfill")
    )
    monkeypatch.setattr("main.process_news_run", lambda runtime: calls.append("news"))
    monkeypatch.setattr(
        "main.process_course_run", lambda runtime: calls.append("course")
    )

    assert run() == 0
    assert calls == ["course"]


def test_run_skips_course_delivery_when_course_service_is_disabled(
    monkeypatch, tmp_path
):
    calls = []
    settings = make_settings(tmp_path)
    settings.enable_course_service = False

    monkeypatch.setattr("main.load_settings_for_mode", lambda mode: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.cleanup_old_delivery_data", lambda _settings, _store, _now: None
    )
    monkeypatch.setattr("main.retry_failed_deliveries_for_today", lambda *_args: set())
    monkeypatch.setattr("main.send_backfill_if_needed", lambda *_args: None)
    monkeypatch.setattr(
        "main.process_course_run", lambda runtime: calls.append("course")
    )
    monkeypatch.setattr("main.process_news_run", lambda runtime: calls.append("news"))

    assert run() == 0
    assert calls == ["news"]


def test_run_noon_records_sent_notice_urls(monkeypatch, tmp_path: Path):
    settings = make_settings(tmp_path)
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 19, 9, 0),
            source="本科生院",
            content="正文",
        )
    ]

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点1")
    sent = []

    def fake_send_email(_settings, subject, body, html_body):
        sent.append({"subject": subject, "body": body, "html": html_body})

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0

    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    record = store.get_record("2026-03-19", "noon")
    assert record is not None
    assert record["email_sent"] is True
    assert record["notice_urls"] == ["http://example.com/a"]
    assert any("每日摘要" in item["html"] for item in sent)


def test_run_evening_skips_when_no_new_notices(monkeypatch, tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-19",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260319.md"),
            email_sent=True,
            notice_urls=["http://example.com/a"],
            status="sent",
        )
    )
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 19, 9, 0),
            source="本科生院",
            content="正文",
        )
    ]
    sent = {"count": 0}

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 18, 0)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr(
        "main.send_email",
        lambda _settings, subject, body, html_body=None: sent.__setitem__(
            "count", sent["count"] + 1
        ),
    )

    assert run() == 0
    assert sent["count"] == 1
    evening = store.get_record("2026-03-19", "evening")
    assert evening is not None
    assert evening["status"] == "skipped_no_new"


def test_run_evening_sends_when_new_notices_exist(monkeypatch, tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-19",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260319.md"),
            email_sent=True,
            notice_urls=["http://example.com/a"],
            status="sent",
        )
    )
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 19, 9, 0),
            source="本科生院",
            content="正文",
        ),
        NoticeItem(
            title="通知B",
            url="http://example.com/b",
            publish_time=datetime(2026, 3, 19, 17, 30),
            source="本科生院",
            content="正文B",
        ),
    ]
    sent = []

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 18, 0)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 新增")

    def fake_send_email(_settings, subject, body, html_body):
        sent.append({"subject": subject, "body": body, "html": html_body})

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert len(sent) == 2
    assert any("晚间通知更新" in item["subject"] for item in sent)
    assert any("晚间更新" in item["html"] for item in sent)


def test_run_sends_news_and_course_task_emails_in_same_run(monkeypatch, tmp_path: Path):
    import main

    settings = make_settings(tmp_path)
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 19, 9, 0),
            source="本科生院",
            content="正文",
        )
    ]
    sent = []

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点1")
    monkeypatch.setattr(main, "fetch_course_tasks", lambda _settings: [], raising=False)

    def fake_send_email(_settings, subject, body, html_body):
        sent.append((subject, body, html_body))

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert len(sent) == 2


def test_run_sends_empty_course_task_email_when_no_tasks(monkeypatch, tmp_path: Path):
    import main

    settings = make_settings(tmp_path)
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 19, 9, 0),
            source="本科生院",
            content="正文",
        )
    ]
    sent = {"subjects": [], "bodies": []}

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点1")
    monkeypatch.setattr(main, "fetch_course_tasks", lambda _settings: [], raising=False)

    def fake_send_email(_settings, subject, body, html_body):
        sent["subjects"].append(subject)
        sent["bodies"].append(body)

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert any("课程任务提醒" in subject for subject in sent["subjects"])
    assert any("今日没有待完成任务" in body for body in sent["bodies"])


def test_run_records_separate_state_for_course_tasks(monkeypatch, tmp_path: Path):
    import main

    settings = make_settings(tmp_path)
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 19, 9, 0),
            source="本科生院",
            content="正文",
        )
    ]

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点1")
    monkeypatch.setattr(main, "fetch_course_tasks", lambda _settings: [], raising=False)
    monkeypatch.setattr(
        "main.send_email", lambda _settings, subject, body, html_body: None
    )

    assert run() == 0

    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    assert store.get_record("2026-03-19", "noon") is not None
    assert store.get_record("2026-03-19", "course_tasks_noon") is not None


def test_run_sends_course_tasks_even_outside_scheduled_windows(
    monkeypatch, tmp_path: Path
):
    import main

    settings = make_settings(tmp_path)
    sent = []

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 11, 30)
    )
    monkeypatch.setattr(main, "fetch_course_tasks", lambda _settings: [], raising=False)

    def fake_send_email(_settings, subject, body, html_body):
        sent.append({"subject": subject, "body": body, "html": html_body})

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert len(sent) == 1
    assert sent[0]["subject"] == "WHUT 课程任务提醒 2026-03-19"

    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    assert store.get_record("2026-03-19", "noon") is None
    assert store.get_record("2026-03-19", "course_tasks_manual") is not None


def test_course_task_failure_does_not_block_news_email(monkeypatch, tmp_path: Path):
    import main

    settings = make_settings(tmp_path)
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 19, 9, 0),
            source="本科生院",
            content="正文",
        )
    ]
    sent = {"count": 0}

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点1")

    def failing_fetch(_settings):
        raise RuntimeError("course fetch failed")

    def fake_send_email(_settings, subject, body, html_body):
        sent["count"] += 1

    monkeypatch.setattr(main, "fetch_course_tasks", failing_fetch, raising=False)
    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert sent["count"] >= 1


def test_news_failure_does_not_block_course_task_email(monkeypatch, tmp_path: Path):
    import main

    settings = make_settings(tmp_path)
    sent = {"count": 0}

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )

    def failing_collect(_settings, _date):
        raise RuntimeError("news collect failed")

    def fake_send_email(_settings, subject, body, html_body):
        sent["count"] += 1

    monkeypatch.setattr("main.collect_notices_for_date", failing_collect)
    monkeypatch.setattr(main, "fetch_course_tasks", lambda _settings: [], raising=False)
    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert sent["count"] >= 1


def test_run_sends_single_backfill_email_for_multiple_missing_days(
    monkeypatch, tmp_path: Path
):
    settings = make_settings(tmp_path)
    settings.backfill_max_days = 3
    sent = []

    notices_by_day = {
        "2026-03-17": [
            NoticeItem(
                title="通知A",
                url="http://example.com/a",
                publish_time=datetime(2026, 3, 17, 9, 0),
                source="本科生院",
                content="正文A",
            )
        ],
        "2026-03-18": [
            NoticeItem(
                title="通知B",
                url="http://example.com/b",
                publish_time=datetime(2026, 3, 18, 9, 0),
                source="本科生院",
                content="正文B",
            )
        ],
        "2026-03-19": [],
    }

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 18, 0)
    )

    def fake_collect(_settings, target_date):
        return notices_by_day[target_date.date().isoformat()]

    monkeypatch.setattr("main.collect_notices_for_date", fake_collect)
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点")

    def fake_send_email(_settings, subject, body, html_body):
        sent.append({"subject": subject, "body": body, "html": html_body})

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert len(sent) == 2
    backfill = next(
        item for item in sent if item["subject"].startswith("WHUT 本科生院通知补发")
    )
    assert "2026-03-17" in backfill["body"]
    assert "2026-03-18" in backfill["body"]
    assert "2026-03-17" in backfill["html"]
    assert "2026-03-18" in backfill["html"]
    files = list(tmp_path.glob("补发_summary_*.md"))
    assert len(files) == 1


def test_failed_email_attempt_is_marked_for_warning_and_retry(
    monkeypatch, tmp_path: Path
):
    settings = make_settings(tmp_path)
    notices = [
        NoticeItem(
            title="通知A",
            url="http://example.com/a",
            publish_time=datetime(2026, 3, 19, 9, 0),
            source="本科生院",
            content="正文",
        )
    ]

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点1")
    monkeypatch.setattr(
        "main.send_email",
        lambda _settings, subject, body, html_body: (_ for _ in ()).throw(
            smtplib.SMTPException("smtp failed")
        ),
    )

    assert run() == 0
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    record = store.get_record("2026-03-19", "noon")
    assert record is not None
    assert record["email_sent"] is False
    assert record["warning_emitted"] is True


def test_run_retries_todays_failed_noon_email(monkeypatch, tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=False,
            notice_urls=["http://example.com/a"],
            status="failed",
            warning_emitted=True,
        )
    )
    sent = {"count": 0}

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 20, 12, 5)
    )
    monkeypatch.setattr("main.collect_notices_for_date", lambda _settings, _date: [])

    def fake_send_email(_settings, subject, body, html_body):
        sent["count"] += 1

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert sent["count"] == 2
    record = store.get_record("2026-03-20", "noon")
    assert record is not None
    assert record["email_sent"] is True
    assert record["status"] == "sent"


def test_run_does_not_send_twice_after_retrying_failed_noon(
    monkeypatch, tmp_path: Path
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=False,
            notice_urls=["http://example.com/a"],
            status="failed",
            warning_emitted=True,
        )
    )
    sent = {"count": 0}

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 20, 12, 0)
    )
    monkeypatch.setattr("main.collect_notices_for_date", lambda _settings, _date: [])

    def fake_send_email(_settings, subject, body, html_body):
        sent["count"] += 1

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert sent["count"] == 2


def test_run_retry_failed_noon_uses_noon_cutoff_for_notice_urls(
    monkeypatch, tmp_path: Path
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=False,
            notice_urls=["http://example.com/old"],
            status="failed",
            warning_emitted=True,
        )
    )
    notices = [
        NoticeItem(
            title="上午通知",
            url="http://example.com/morning",
            publish_time=datetime(2026, 3, 20, 11, 0),
            source="本科生院",
            content="上午正文",
        ),
        NoticeItem(
            title="下午通知",
            url="http://example.com/afternoon",
            publish_time=datetime(2026, 3, 20, 17, 0),
            source="本科生院",
            content="下午正文",
        ),
    ]

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 20, 18, 5)
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点")
    monkeypatch.setattr(
        "main.send_email", lambda _settings, subject, body, html_body: None
    )

    assert run() == 0
    record = store.get_record("2026-03-20", "noon")
    assert record is not None
    assert record["notice_urls"] == ["http://example.com/morning"]


def test_run_retry_failed_noon_supports_aware_now_with_naive_notice_times(
    monkeypatch, tmp_path: Path
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=False,
            notice_urls=[],
            status="failed",
            warning_emitted=True,
        )
    )
    notices = [
        NoticeItem(
            title="上午通知",
            url="http://example.com/morning",
            publish_time=datetime(2026, 3, 20, 11, 0),
            source="本科生院",
            content="上午正文",
        )
    ]

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time",
        lambda _settings: datetime(
            2026, 3, 20, 18, 5, tzinfo=ZoneInfo("Asia/Shanghai")
        ),
    )
    monkeypatch.setattr(
        "main.collect_notices_for_date", lambda _settings, _date: notices
    )
    monkeypatch.setattr("main.enrich_notice_content", lambda ns, timeout: ns)
    monkeypatch.setattr("main.summarize_with_deepseek", lambda ns, _settings: "- 要点")
    monkeypatch.setattr(
        "main.send_email", lambda _settings, subject, body, html_body: None
    )

    assert run() == 0
    record = store.get_record("2026-03-20", "noon")
    assert record is not None
    assert record["email_sent"] is True


def test_retry_failed_deliveries_for_today_retries_partial_napcat_evening_success(
    monkeypatch, tmp_path: Path
):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="evening",
            summary_path=str(tmp_path / "summary_20260320_evening.md"),
            email_sent=True,
            notice_urls=["http://example.com/a"],
            status="sent",
            napcat_sent=False,
            napcat_error="group:123456: timeout",
            napcat_target_results=[
                {"target": "group:123456", "sent": False, "error": "timeout"},
                {"target": "private:987654", "sent": True, "error": ""},
            ],
        )
    )
    attempted: list[str] = []

    monkeypatch.setattr(
        "main.process_evening_delivery",
        lambda _settings, _store, _now: attempted.append("evening") or 0,
    )

    from main import retry_failed_deliveries_for_today

    result = retry_failed_deliveries_for_today(
        settings,
        store,
        datetime(2026, 3, 20, 18, 5),
    )

    assert result == {"evening"}
    assert attempted == ["evening"]


def test_run_does_not_retry_failed_noon_twice_in_same_scheduled_run(
    monkeypatch, tmp_path: Path
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=False,
            notice_urls=["http://example.com/a"],
            status="failed",
            warning_emitted=True,
        )
    )
    sent = {"count": 0}

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 20, 12, 0)
    )
    monkeypatch.setattr("main.collect_notices_for_date", lambda _settings, _date: [])

    def fake_send_email(_settings, subject, body, html_body):
        sent["count"] += 1
        raise smtplib.SMTPException("smtp failed")

    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert sent["count"] == 2


def test_run_skips_duplicate_successful_noon_send(monkeypatch, tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-19",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260319.md"),
            email_sent=True,
            notice_urls=["http://example.com/a"],
            status="sent",
        )
    )
    called = {"send": 0}

    monkeypatch.setattr("main.Settings.from_env", lambda **_kwargs: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 5)
    )
    monkeypatch.setattr(
        "main.send_email",
        lambda _settings, subject, body, html_body=None: called.__setitem__(
            "send", called["send"] + 1
        ),
    )

    assert run() == 0
    assert called["send"] == 1


def test_process_course_task_delivery_sends_again_after_same_day_success(
    monkeypatch, tmp_path: Path
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-19",
            slot="course_tasks_noon",
            summary_path=str(tmp_path / "summary_20260319.md"),
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )
    sent = {"count": 0}
    latest_artifact = tmp_path / "course_tasks_20260319_noon.md"

    def fake_send_course_task_email(_settings, target_date, slot):
        sent["count"] += 1
        assert target_date == datetime(2026, 3, 19, 12, 0)
        assert slot == "noon"
        return ("课程提醒", "更新正文", "<p>更新正文</p>")

    monkeypatch.setattr("main.send_course_task_email", fake_send_course_task_email)
    monkeypatch.setattr(
        "main.write_course_task_artifact_service",
        lambda *_args: latest_artifact,
    )

    process_course_task_delivery(settings, store, datetime(2026, 3, 19, 12, 0), "noon")

    record = store.get_record("2026-03-19", "course_tasks_noon")

    assert sent["count"] == 1
    assert record is not None
    assert record["summary_path"] == str(latest_artifact)
    assert record["email_sent"] is True
    assert record["status"] == "sent"
