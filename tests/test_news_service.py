from datetime import datetime
from pathlib import Path

from config import Settings
from delivery_state import DeliveryRecord, DeliveryStateStore
from models import NoticeItem
from services.news_service import (
    process_evening_delivery,
    process_news_delivery_safely,
    process_noon_delivery,
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
        backfill_max_days=1,
        state_retention_days=15,
    )


def test_process_news_delivery_safely_rejects_unknown_slot(tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 15, 30)
    calls: list[str] = []
    saved: dict[str, object] = {}
    printed: list[str] = []

    def process_noon(*_args):
        calls.append("noon")
        return 0

    def process_evening(*_args):
        calls.append("evening")
        return 0

    def save_delivery_record(*args, **kwargs):
        saved["args"] = args
        saved["kwargs"] = kwargs

    def get_summary_file_path(
        output_dir: str, when: datetime | None, slot: str
    ) -> Path:
        assert output_dir == str(tmp_path)
        assert when == datetime(2026, 3, 20, 0, 0)
        return Path(output_dir) / f"summary_{slot}.md"

    process_news_delivery_safely(
        settings,
        store,
        now,
        "afternoon",
        process_noon_delivery_fn=process_noon,
        process_evening_delivery_fn=process_evening,
        save_delivery_record_fn=save_delivery_record,
        get_summary_file_path_for_date_fn=get_summary_file_path,
        print_fn=printed.append,
    )

    assert calls == []
    assert printed[-1] == "[WARN] 新闻邮件流程失败: 不支持的新闻投递时段: afternoon"
    assert saved["args"] == (
        store,
        datetime(2026, 3, 20, 0, 0),
        "afternoon",
        tmp_path / "summary_afternoon.md",
        [],
        False,
        "failed",
    )
    assert saved["kwargs"] == {"warning_emitted": True}


def test_process_evening_delivery_uses_injected_summary_writer(tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 17, 30),
        )
    ]
    output_path = tmp_path / "summary_20260320_evening.md"
    write_calls: list[tuple[str, str, datetime | None, str]] = []
    email_calls: list[tuple[str, str, str]] = []
    saved: dict[str, object] = {}
    printed: list[str] = []

    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )

    def collect_notices(_settings: Settings, target_date: datetime) -> list[NoticeItem]:
        assert target_date == datetime(2026, 3, 20, 0, 0)
        return notices

    def build_notice_outputs(
        _settings: Settings, items, target_date: datetime, slot: str
    ):
        assert items == notices
        assert target_date == datetime(2026, 3, 20, 0, 0)
        assert slot == "evening"
        return ("# summary\n", "body", "<p>body</p>", items, [items[0].url])

    def write_summary_file(
        text: str, output_dir: str, when: datetime | None, slot: str
    ) -> Path:
        write_calls.append((text, output_dir, when, slot))
        return output_path

    def build_email_subject(_source: str, target_date: datetime, slot: str) -> str:
        assert target_date == datetime(2026, 3, 20, 0, 0)
        assert slot == "evening"
        return "subject"

    def send_email(_settings: Settings, subject: str, body: str, html: str) -> None:
        email_calls.append((subject, body, html))

    def save_delivery_record(*args, **kwargs):
        saved["args"] = args
        saved["kwargs"] = kwargs

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(
            AssertionError("direct path lookup should not be used for written summary")
        ),
        collect_notices_for_date_fn=collect_notices,
        build_notice_outputs_fn=build_notice_outputs,
        write_summary_file_fn=write_summary_file,
        build_email_subject_fn=build_email_subject,
        send_email_fn=send_email,
        send_napcat_message_fn=lambda *_args: None,
        build_napcat_news_message_fn=lambda _markdown, _items: "unused",
        save_delivery_record_fn=save_delivery_record,
        print_fn=printed.append,
    )

    assert write_calls == [
        ("# summary\n", str(tmp_path), datetime(2026, 3, 20, 0, 0), "evening")
    ]
    assert email_calls == [("subject", "body", "<p>body</p>")]
    assert saved["args"] == (
        store,
        datetime(2026, 3, 20, 0, 0),
        "evening",
        output_path,
        ["https://example.com/new"],
        True,
        "sent",
    )
    assert saved["kwargs"] == {
        "warning_emitted": False,
        "now": now,
        "napcat_sent": False,
        "napcat_error": "",
        "napcat_target_results": [],
    }
    assert printed[-2:] == ["邮件已发送到: receiver@example.com", f"\n已写入: {output_path}"]


def test_process_evening_delivery_sends_napcat_to_all_targets_when_enabled(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456", "private:987654"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 17, 30),
        )
    ]
    napcat_calls: list[tuple[str, str]] = []

    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "unused.md",
        collect_notices_for_date_fn=lambda *_args: notices,
        build_notice_outputs_fn=lambda *_args: (
            "# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **new notice**\n",
            "body",
            "<p>body</p>",
            notices,
            [notices[0].url],
        ),
        write_summary_file_fn=lambda *_args, **_kwargs: tmp_path / "summary_20260320_evening.md",
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: None,
        send_napcat_message_fn=lambda _settings, target, message: napcat_calls.append(
            (target, message)
        ),
        build_napcat_news_message_fn=lambda markdown, items: (
            f"qq::{len(items)}::{markdown.splitlines()[-1]}"
        ),
        save_delivery_record_fn=lambda *args, **kwargs: None,
    )

    assert napcat_calls == [
        ("group:123456", "qq::1::1. **new notice**"),
        ("private:987654", "qq::1::1. **new notice**"),
    ]


def test_process_evening_delivery_records_partial_napcat_failures(tmp_path: Path):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456", "private:987654"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    saved: dict[str, object] = {}
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 17, 30),
        )
    ]

    def fake_send_napcat(_settings: Settings, target: str, _message: str) -> None:
        if target == "group:123456":
            raise RuntimeError("timeout")

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "unused.md",
        collect_notices_for_date_fn=lambda *_args: notices,
        build_notice_outputs_fn=lambda *_args: (
            "# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **new notice**\n",
            "body",
            "<p>body</p>",
            notices,
            [notices[0].url],
        ),
        write_summary_file_fn=lambda *_args, **_kwargs: tmp_path / "summary_20260320_evening.md",
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: None,
        send_napcat_message_fn=fake_send_napcat,
        build_napcat_news_message_fn=lambda markdown, items: (
            f"qq::{len(items)}::{markdown.splitlines()[-1]}"
        ),
        save_delivery_record_fn=lambda *args, **kwargs: saved.update(
            {"args": args, "kwargs": kwargs}
        ),
    )

    assert saved["kwargs"]["napcat_sent"] is False
    assert saved["kwargs"]["napcat_error"] == "group:123456: timeout"
    assert saved["kwargs"]["napcat_target_results"] == [
        {"target": "group:123456", "sent": False, "error": "timeout"},
        {"target": "private:987654", "sent": True, "error": ""},
    ]
    assert saved["args"][6] == "sent"


def test_process_evening_delivery_still_attempts_napcat_after_email_failure(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    napcat_calls: list[tuple[str, str]] = []
    saved: dict[str, object] = {}
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 17, 30),
        )
    ]

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "unused.md",
        collect_notices_for_date_fn=lambda *_args: notices,
        build_notice_outputs_fn=lambda *_args: (
            "# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **new notice**\n",
            "body",
            "<p>body</p>",
            notices,
            [notices[0].url],
        ),
        write_summary_file_fn=lambda *_args, **_kwargs: tmp_path / "summary_20260320_evening.md",
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: (_ for _ in ()).throw(RuntimeError("smtp down")),
        send_napcat_message_fn=lambda _settings, target, message: napcat_calls.append(
            (target, message)
        ),
        build_napcat_news_message_fn=lambda markdown, items: (
            f"qq::{len(items)}::{markdown.splitlines()[-1]}"
        ),
        save_delivery_record_fn=lambda *args, **kwargs: saved.update(
            {"args": args, "kwargs": kwargs}
        ),
    )

    assert napcat_calls == [("group:123456", "qq::1::1. **new notice**")]
    assert saved["kwargs"]["napcat_sent"] is True
    assert saved["args"][5] is False
    assert saved["args"][6] == "sent"


def test_process_evening_delivery_skips_when_napcat_only_success_already_recorded(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 5)
    calls: list[str] = []
    printed: list[str] = []

    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="evening",
            summary_path=str(tmp_path / "summary_20260320_evening.md"),
            email_sent=False,
            notice_urls=["https://example.com/new"],
            status="sent",
            napcat_sent=True,
            napcat_target_results=[
                {"target": "group:123456", "sent": True, "error": ""}
            ],
        )
    )

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "unused.md",
        collect_notices_for_date_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should not recollect notices")
        ),
        build_notice_outputs_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should not rebuild outputs")
        ),
        write_summary_file_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should not rewrite summary")
        ),
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: calls.append("email"),
        send_napcat_message_fn=lambda *_args: calls.append("napcat"),
        build_napcat_news_message_fn=lambda *_args: "unused",
        save_delivery_record_fn=lambda *_args, **_kwargs: calls.append("save"),
        print_fn=printed.append,
    )

    assert calls == []
    assert printed[-1] == "当天晚间通知已成功发送，跳过重复发送"


def test_process_evening_delivery_retries_only_failed_napcat_targets_after_email_success(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456", "private:987654"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 5)
    summary_path = tmp_path / "summary_20260320_evening.md"
    summary_path.write_text(
        "# 本科生院最近三天通知总结\n\n"
        "## 摘要\n\n"
        "1. **new notice**\n\n"
        "## 涉及通知\n\n"
        "- `2026-03-20` [new notice](https://example.com/new)\n",
        encoding="utf-8",
    )
    napcat_calls: list[tuple[str, str]] = []
    printed: list[str] = []

    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="evening",
            summary_path=str(summary_path),
            email_sent=True,
            notice_urls=["https://example.com/new"],
            status="sent",
            napcat_sent=False,
            napcat_error="group:123456: timeout",
            napcat_target_results=[
                {"target": "group:123456", "sent": False, "error": "timeout"},
                {"target": "private:987654", "sent": True, "error": ""},
            ],
        )
    )

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "unused.md",
        collect_notices_for_date_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should not recollect notices")
        ),
        build_notice_outputs_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should not rebuild outputs")
        ),
        write_summary_file_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should not rewrite summary")
        ),
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should not resend email")
        ),
        send_napcat_message_fn=lambda _settings, target, message: napcat_calls.append(
            (target, message)
        ),
        build_napcat_news_message_fn=lambda markdown, items: (
            f"qq::{len(items)}::{markdown.splitlines()[-1]}"
        ),
        save_delivery_record_fn=lambda *_args, **_kwargs: None,
        print_fn=printed.append,
    )

    assert napcat_calls == [
        ("group:123456", "qq::0::- `2026-03-20` [new notice](https://example.com/new)")
    ]
    assert "当天晚间邮件已成功发送，跳过重复发送" in printed


def test_process_evening_delivery_retries_pending_napcat_with_existing_summary_when_no_new_notices(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456", "private:987654"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 19, 0)
    summary_path = tmp_path / "summary_20260320_evening.md"
    summary_path.write_text(
        "# 本科生院最近三天通知总结\n\n"
        "## 摘要\n\n"
        "1. **new notice**\n\n"
        "## 涉及通知\n\n"
        "- `2026-03-20` [new notice](https://example.com/new)\n",
        encoding="utf-8",
    )
    napcat_calls: list[tuple[str, str]] = []
    saved: dict[str, object] = {}
    printed: list[str] = []

    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="evening",
            summary_path=str(summary_path),
            email_sent=True,
            notice_urls=["https://example.com/new"],
            status="sent",
            napcat_sent=False,
            napcat_error="group:123456: timeout",
            napcat_target_results=[
                {"target": "group:123456", "sent": False, "error": "timeout"},
                {"target": "private:987654", "sent": True, "error": ""},
            ],
        )
    )

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "unused.md",
        collect_notices_for_date_fn=lambda *_args: [],
        build_notice_outputs_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should not rebuild outputs")
        ),
        write_summary_file_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should not rewrite summary")
        ),
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should not resend email")
        ),
        send_napcat_message_fn=lambda _settings, target, message: napcat_calls.append(
            (target, message)
        ),
        build_napcat_news_message_fn=lambda markdown, items: (
            f"qq::{len(items)}::{markdown.splitlines()[-1]}"
        ),
        save_delivery_record_fn=lambda *args, **kwargs: saved.update(
            {"args": args, "kwargs": kwargs}
        ),
        print_fn=printed.append,
    )

    assert napcat_calls == [("group:123456", "qq::0::- `2026-03-20` [new notice](https://example.com/new)")]
    assert saved["args"][5] is True
    assert saved["args"][6] == "sent"
    assert saved["kwargs"]["napcat_sent"] is True
    assert printed[-1] == f"\n已写入: {summary_path}"


def test_process_noon_delivery_never_sends_napcat(tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 12, 0)
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 11, 30),
        )
    ]

    process_noon_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "summary.md",
        collect_notices_for_date_fn=lambda *_args: notices,
        trim_notices_to_cutoff_fn=lambda items, *_args: items,
        build_notice_outputs_fn=lambda *_args: (
            "# summary\n",
            "body",
            "<p>body</p>",
            notices,
            [notices[0].url],
        ),
        write_summary_file_fn=lambda *_args, **_kwargs: tmp_path / "summary.md",
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: None,
        save_delivery_record_fn=lambda *_args, **_kwargs: None,
    )


def test_process_noon_delivery_records_written_summary_path_on_send_failure(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 12, 0)
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 11, 30),
        )
    ]
    output_path = tmp_path / "writer_selected_20260320.md"
    write_calls: list[tuple[str, str, datetime | None]] = []
    saved: dict[str, object] = {}
    printed: list[str] = []

    def get_summary_file_path(*_args, **_kwargs) -> Path:
        return tmp_path / "precomputed_20260320.md"

    def collect_notices(_settings: Settings, target_date: datetime) -> list[NoticeItem]:
        assert target_date == datetime(2026, 3, 20, 0, 0)
        return notices

    def trim_notices(items, target_date: datetime, hour: int, minute: int):
        assert items == notices
        assert target_date == datetime(2026, 3, 20, 0, 0)
        assert (hour, minute) == (12, 0)
        return items

    def build_notice_outputs(
        _settings: Settings, items, target_date: datetime, slot: str
    ):
        assert items == notices
        assert target_date == datetime(2026, 3, 20, 0, 0)
        assert slot == "noon"
        return ("# summary\n", "body", "<p>body</p>", items, [items[0].url])

    def write_summary_file(text: str, output_dir: str, when: datetime | None) -> Path:
        write_calls.append((text, output_dir, when))
        return output_path

    def build_email_subject(_source: str, target_date: datetime, slot: str) -> str:
        assert target_date == datetime(2026, 3, 20, 0, 0)
        assert slot == "noon"
        return "subject"

    def send_email(_settings: Settings, _subject: str, _body: str, _html: str) -> None:
        raise RuntimeError("smtp down")

    def save_delivery_record(*args, **kwargs):
        saved["args"] = args
        saved["kwargs"] = kwargs

    process_noon_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=get_summary_file_path,
        collect_notices_for_date_fn=collect_notices,
        trim_notices_to_cutoff_fn=trim_notices,
        build_notice_outputs_fn=build_notice_outputs,
        write_summary_file_fn=write_summary_file,
        build_email_subject_fn=build_email_subject,
        send_email_fn=send_email,
        save_delivery_record_fn=save_delivery_record,
        print_fn=printed.append,
    )

    assert write_calls == [("# summary\n", str(tmp_path), datetime(2026, 3, 20, 0, 0))]
    assert saved["args"] == (
        store,
        datetime(2026, 3, 20, 0, 0),
        "noon",
        output_path,
        ["https://example.com/new"],
        False,
        "failed",
    )
    assert saved["kwargs"] == {
        "warning_emitted": True,
        "now": now,
    }
    assert printed[-2:] == ["[WARN] 邮件发送失败: smtp down", f"\n已写入: {output_path}"]
