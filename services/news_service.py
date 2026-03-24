import smtplib
from datetime import datetime
from pathlib import Path
from typing import Callable

from config import Settings
from delivery_state import DeliveryStateStore
from models import NoticeItem


def process_news_delivery_safely(
    settings: Settings,
    store: DeliveryStateStore,
    now: datetime,
    slot: str,
    *,
    process_noon_delivery_fn: Callable[[Settings, DeliveryStateStore, datetime], int],
    process_evening_delivery_fn: Callable[
        [Settings, DeliveryStateStore, datetime], int
    ],
    save_delivery_record_fn: Callable[..., None],
    get_summary_file_path_for_date_fn: Callable[..., Path],
    print_fn: Callable[[str], None] = print,
) -> None:
    target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        if slot == "evening":
            process_evening_delivery_fn(settings, store, now)
        elif slot == "noon":
            process_noon_delivery_fn(settings, store, now)
        else:
            raise ValueError(f"不支持的新闻投递时段: {slot}")
    except (ValueError, RuntimeError, smtplib.SMTPException, OSError) as exc:
        print_fn(f"[WARN] 新闻邮件流程失败: {exc}")
        save_delivery_record_fn(
            store,
            target_date,
            slot,
            get_summary_file_path_for_date_fn(settings.output_dir, target_date, slot),
            [],
            False,
            "failed",
            warning_emitted=True,
        )


def process_noon_delivery(
    settings: Settings,
    store: DeliveryStateStore,
    now: datetime,
    *,
    get_summary_file_path_for_date_fn: Callable[..., Path],
    collect_notices_for_date_fn: Callable[[Settings, datetime], list[NoticeItem]],
    trim_notices_to_cutoff_fn: Callable[
        [list[NoticeItem], datetime, int, int], list[NoticeItem]
    ],
    build_notice_outputs_fn: Callable[
        ..., tuple[str, str, str, list[NoticeItem], list[str]]
    ],
    write_summary_file_fn: Callable[[str, str, datetime | None], Path],
    build_email_subject_fn: Callable[[str, datetime, str], str],
    send_email_fn: Callable[[Settings, str, str, str], None],
    save_delivery_record_fn: Callable[..., None],
    print_fn: Callable[[str], None] = print,
) -> int:
    target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    existing = store.get_record(target_date.date().isoformat(), "noon")
    if existing and bool(existing.get("email_sent")):
        print_fn("当天中午邮件已成功发送，跳过重复发送")
        return 0
    notices = collect_notices_for_date_fn(settings, target_date)
    notices = trim_notices_to_cutoff_fn(
        notices, target_date, settings.schedule_hour, settings.schedule_minute
    )
    markdown, body, html, _items, notice_urls = build_notice_outputs_fn(
        settings, notices, target_date, "noon"
    )
    output = write_summary_file_fn(markdown, settings.output_dir, target_date)
    subject = build_email_subject_fn(settings.target_source, target_date, "noon")

    try:
        send_email_fn(settings, subject, body, html)
        print_fn(f"邮件已发送到: {settings.email_to}")
        save_delivery_record_fn(
            store, target_date, "noon", output, notice_urls, True, "sent", now=now
        )
    except (ValueError, RuntimeError, smtplib.SMTPException, OSError) as exc:
        print_fn(f"[WARN] 邮件发送失败: {exc}")
        save_delivery_record_fn(
            store,
            target_date,
            "noon",
            output,
            notice_urls,
            False,
            "failed",
            warning_emitted=True,
            now=now,
        )

    print_fn(f"\n已写入: {output}")
    return 0


def process_evening_delivery(
    settings: Settings,
    store: DeliveryStateStore,
    now: datetime,
    *,
    get_summary_file_path_for_date_fn: Callable[..., Path],
    collect_notices_for_date_fn: Callable[[Settings, datetime], list[NoticeItem]],
    build_notice_outputs_fn: Callable[
        ..., tuple[str, str, str, list[NoticeItem], list[str]]
    ],
    write_summary_file_fn: Callable[..., Path],
    build_email_subject_fn: Callable[[str, datetime, str], str],
    send_email_fn: Callable[[Settings, str, str, str], None],
    save_delivery_record_fn: Callable[..., None],
    print_fn: Callable[[str], None] = print,
) -> int:
    target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    existing = store.get_record(target_date.date().isoformat(), "evening")
    if existing and bool(existing.get("email_sent")):
        print_fn("当天晚间邮件已成功发送，跳过重复发送")
        return 0
    notices = collect_notices_for_date_fn(settings, target_date)
    noon_record = store.get_record(target_date.date().isoformat(), "noon") or {}
    noon_notice_urls = noon_record.get("notice_urls", [])
    noon_urls = set(noon_notice_urls if isinstance(noon_notice_urls, list) else [])
    new_notices = [item for item in notices if item.url not in noon_urls]

    if not new_notices:
        save_delivery_record_fn(
            store,
            target_date,
            "evening",
            get_summary_file_path_for_date_fn(
                settings.output_dir, target_date, "evening"
            ),
            [],
            False,
            "skipped_no_new",
            now=now,
        )
        print_fn("今天 18:00 后没有新增通知，跳过发送")
        return 0

    markdown, body, html, _items, notice_urls = build_notice_outputs_fn(
        settings, new_notices, target_date, "evening"
    )
    evening_output = write_summary_file_fn(
        markdown,
        settings.output_dir,
        target_date,
        "evening",
    )
    subject = build_email_subject_fn(settings.target_source, target_date, "evening")

    try:
        send_email_fn(settings, subject, body, html)
        print_fn(f"邮件已发送到: {settings.email_to}")
        save_delivery_record_fn(
            store,
            target_date,
            "evening",
            evening_output,
            notice_urls,
            True,
            "sent",
            now=now,
        )
    except (ValueError, RuntimeError, smtplib.SMTPException, OSError) as exc:
        print_fn(f"[WARN] 邮件发送失败: {exc}")
        save_delivery_record_fn(
            store,
            target_date,
            "evening",
            evening_output,
            notice_urls,
            False,
            "failed",
            warning_emitted=True,
            now=now,
        )

    print_fn(f"\n已写入: {evening_output}")
    return 0
