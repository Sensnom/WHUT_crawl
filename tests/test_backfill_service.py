from datetime import datetime
from pathlib import Path

from config import Settings
from delivery_state import DeliveryStateStore
from models import NoticeItem
from services.backfill_service import send_backfill_if_needed


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
        backfill_max_days=3,
        state_retention_days=15,
    )


def test_send_backfill_if_needed_trims_today_and_records_each_missing_day(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    calls = {"trim": [], "saved": [], "sent": []}

    def collect_notices(_settings: Settings, target_date: datetime) -> list[NoticeItem]:
        return [
            NoticeItem(
                title=f"通知-{target_date:%Y%m%d}",
                url=f"https://example.com/{target_date:%Y%m%d}",
                publish_time=target_date.replace(hour=17, minute=30),
                source="本科生院",
                content="正文",
            )
        ]

    def trim_notices(notices, target_date, cutoff_hour, cutoff_minute):
        calls["trim"].append((target_date, cutoff_hour, cutoff_minute, len(notices)))
        return notices[:0]

    def build_notice_outputs(_settings: Settings, notices, target_date: datetime):
        markdown = f"# {target_date.date().isoformat()}\n{len(notices)} notices"
        return (
            markdown,
            f"body-{len(notices)}",
            "<p>html</p>",
            notices,
            [n.url for n in notices],
        )

    def write_summary_file(
        markdown: str, output_dir: str, target_date: datetime | None
    ) -> Path:
        assert target_date is not None
        path = Path(output_dir) / f"summary_{target_date:%Y%m%d}.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def build_backfill_markdown(output_dir: str, date_sections: dict[str, str]):
        path = Path(output_dir) / "backfill.md"
        body = "\n\n".join(date_sections.values())
        path.write_text(body, encoding="utf-8")
        return path, body

    send_backfill_if_needed(
        settings,
        store,
        datetime(2026, 3, 20, 18, 0),
        True,
        collect_notices_for_date_fn=collect_notices,
        trim_notices_to_cutoff_fn=trim_notices,
        build_notice_outputs_fn=build_notice_outputs,
        write_summary_file_fn=write_summary_file,
        build_backfill_markdown_fn=build_backfill_markdown,
        build_backfill_subject_fn=lambda source, start_date, end_date: (
            f"{source}:{start_date}->{end_date}"
        ),
        build_backfill_html_fn=lambda *_args: "<p>backfill</p>",
        send_email_fn=lambda _settings, subject, body, html: calls["sent"].append(
            (subject, body, html)
        ),
        save_delivery_record_fn=lambda *args, **kwargs: calls["saved"].append(
            (args, kwargs)
        ),
    )

    assert calls["trim"] == [(datetime(2026, 3, 20, 0, 0), 12, 0, 1)]
    assert len(calls["sent"]) == 1
    assert len(calls["saved"]) == 3
    assert calls["saved"][0][0][1].date().isoformat() == "2026-03-18"
    assert calls["saved"][1][0][1].date().isoformat() == "2026-03-19"
    assert calls["saved"][2][0][1].date().isoformat() == "2026-03-20"
    assert all(item[0][5] is True for item in calls["saved"])
    assert all(
        item[1] == {"backfilled": True, "now": datetime(2026, 3, 20, 18, 0)}
        for item in calls["saved"]
    )


def test_send_backfill_if_needed_marks_each_day_failed_when_email_send_fails(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    settings.backfill_max_days = 2
    store = DeliveryStateStore(tmp_path / "state.json")
    saved: list[tuple[tuple[object, ...], dict[str, object]]] = []
    printed: list[str] = []

    send_backfill_if_needed(
        settings,
        store,
        datetime(2026, 3, 20, 18, 0),
        False,
        collect_notices_for_date_fn=lambda _settings, target_date: [
            NoticeItem(
                title="通知",
                url=f"https://example.com/{target_date:%Y%m%d}",
                publish_time=target_date,
            )
        ],
        trim_notices_to_cutoff_fn=lambda notices, *_args: notices,
        build_notice_outputs_fn=lambda _settings, notices, target_date: (
            f"# {target_date:%Y-%m-%d}",
            "body",
            "<p>html</p>",
            notices,
            [item.url for item in notices],
        ),
        write_summary_file_fn=lambda _markdown, output_dir, target_date: (
            Path(output_dir) / f"summary_{target_date:%Y%m%d}.md"
        ),
        build_backfill_markdown_fn=lambda output_dir, date_sections: (
            Path(output_dir) / "backfill.md",
            "\n".join(date_sections.values()),
        ),
        build_backfill_subject_fn=lambda *_args: "backfill subject",
        build_backfill_html_fn=lambda *_args: "<p>backfill</p>",
        send_email_fn=lambda *_args: (_ for _ in ()).throw(OSError("smtp down")),
        save_delivery_record_fn=lambda *args, **kwargs: saved.append((args, kwargs)),
        print_fn=printed.append,
    )

    assert printed == ["[WARN] 补发邮件发送失败: smtp down"]
    assert len(saved) == 1
    assert saved[0][0][5] is False
    assert saved[0][0][6] == "failed"
    assert saved[0][1] == {
        "warning_emitted": True,
        "backfilled": True,
        "now": datetime(2026, 3, 20, 18, 0),
    }
