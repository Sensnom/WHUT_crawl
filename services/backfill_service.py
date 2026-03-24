import smtplib
from datetime import datetime
from pathlib import Path
from typing import Callable

from config import Settings
from delivery_state import DeliveryStateStore
from models import NoticeItem


def send_backfill_if_needed(
    settings: Settings,
    store: DeliveryStateStore,
    now: datetime,
    include_today: bool,
    *,
    collect_notices_for_date_fn: Callable[[Settings, datetime], list[NoticeItem]],
    trim_notices_to_cutoff_fn: Callable[
        [list[NoticeItem], datetime, int, int], list[NoticeItem]
    ],
    build_notice_outputs_fn: Callable[
        ..., tuple[str, str, str, list[NoticeItem], list[str]]
    ],
    write_summary_file_fn: Callable[[str, str, datetime | None], Path],
    build_backfill_markdown_fn: Callable[[str, dict[str, str]], tuple[Path, str]],
    build_backfill_subject_fn: Callable[[str, str, str], str],
    build_backfill_html_fn: Callable[[str, str, str, dict[str, str]], str],
    send_email_fn: Callable[[Settings, str, str, str], None],
    save_delivery_record_fn: Callable[..., None],
    print_fn: Callable[[str], None] = print,
) -> None:
    end_date = now.date()
    missing_dates = store.missing_noon_dates(
        end_date, settings.backfill_max_days, include_end_date=include_today
    )
    if not missing_dates:
        return

    date_sections: dict[str, str] = {}
    delivery_cache: dict[str, tuple[Path, list[str]]] = {}
    for missing_date in missing_dates:
        target_date = datetime.combine(missing_date, datetime.min.time())
        notices = collect_notices_for_date_fn(settings, target_date)
        if include_today and missing_date == now.date():
            notices = trim_notices_to_cutoff_fn(
                notices, target_date, settings.schedule_hour, settings.schedule_minute
            )
        markdown, _body, _html, _items, notice_urls = build_notice_outputs_fn(
            settings, notices, target_date
        )
        summary_path = write_summary_file_fn(markdown, settings.output_dir, target_date)
        date_sections[missing_date.isoformat()] = markdown
        delivery_cache[missing_date.isoformat()] = (summary_path, notice_urls)

    _backfill_path, backfill_body = build_backfill_markdown_fn(
        settings.output_dir, date_sections
    )
    start_date = min(date_sections)
    end_date_str = max(date_sections)
    subject = build_backfill_subject_fn(
        settings.target_source, start_date, end_date_str
    )
    backfill_html = build_backfill_html_fn(
        settings.target_source, start_date, end_date_str, date_sections
    )

    try:
        send_email_fn(settings, subject, backfill_body, backfill_html)
        print_fn(f"补发邮件已发送到: {settings.email_to}")
        for current_date, (summary_path, notice_urls) in delivery_cache.items():
            save_delivery_record_fn(
                store,
                datetime.fromisoformat(current_date),
                "noon",
                summary_path,
                notice_urls,
                True,
                "sent",
                backfilled=True,
                now=now,
            )
    except (ValueError, RuntimeError, smtplib.SMTPException, OSError) as exc:
        print_fn(f"[WARN] 补发邮件发送失败: {exc}")
        for current_date, (summary_path, notice_urls) in delivery_cache.items():
            save_delivery_record_fn(
                store,
                datetime.fromisoformat(current_date),
                "noon",
                summary_path,
                notice_urls,
                False,
                "failed",
                warning_emitted=True,
                backfilled=True,
                now=now,
            )
