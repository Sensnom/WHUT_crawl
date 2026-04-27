import smtplib
from datetime import datetime
from pathlib import Path
from typing import Callable

from config import Settings
from delivery_state import DeliveryStateStore
from models import NoticeItem


def _send_evening_napcat_notifications(
    settings: Settings,
    markdown: str,
    notices: list[NoticeItem],
    targets: list[str],
    *,
    send_napcat_message_fn: Callable[[Settings, str, str], None],
    build_napcat_news_message_fn: Callable[[str, list[NoticeItem]], str],
    print_fn: Callable[[str], None],
) -> tuple[bool, str, list[dict[str, object]]]:
    if not settings.enable_napcat_service or not targets:
        return False, "", []

    qq_message = build_napcat_news_message_fn(markdown, notices)
    target_results: list[dict[str, object]] = []

    for target in targets:
        print_fn(f"[NEWS_TRACE] napcat_send_start target={target!r}")
        try:
            send_napcat_message_fn(settings, target, qq_message)
            target_results.append({"target": target, "sent": True, "error": ""})
            print_fn(f"[NEWS_TRACE] napcat_send_done target={target!r} sent=True")
        except (RuntimeError, OSError, ValueError) as exc:
            target_results.append(
                {"target": target, "sent": False, "error": str(exc)}
            )
            print_fn(f"[NEWS_TRACE] napcat_send_done target={target!r} sent=False")
            print_fn(f"[WARN] NapCat 发送失败 target={target}: {exc}")

    failed_targets = [item for item in target_results if not bool(item["sent"])]
    napcat_sent = bool(target_results) and not failed_targets
    napcat_error = "; ".join(
        f"{item['target']}: {item['error']}" for item in failed_targets
    )
    return napcat_sent, napcat_error, target_results


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
    print_fn(
        f"[NEWS_TRACE] safe_delivery slot={slot} now={now.isoformat()} target_date={target_date.date().isoformat()}"
    )

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
    print_fn(
        f"[NEWS_TRACE] enter_noon now={now.isoformat()} existing={existing!r}"
    )
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
    print_fn(
        f"[NEWS_TRACE] noon_send subject={subject!r} notices={len(notice_urls)} output={str(output)!r}"
    )

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
    send_napcat_message_fn: Callable[[Settings, str, str], None],
    build_napcat_news_message_fn: Callable[[str, list[NoticeItem]], str],
    save_delivery_record_fn: Callable[..., None],
    print_fn: Callable[[str], None] = print,
) -> int:
    target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    existing = store.get_record(target_date.date().isoformat(), "evening")
    print_fn(
        f"[NEWS_TRACE] enter_evening now={now.isoformat()} existing={existing!r}"
    )
    existing_email_sent = bool(existing.get("email_sent")) if existing else False
    existing_napcat_sent = bool(existing.get("napcat_sent")) if existing else False
    if existing and (
        existing_napcat_sent
        or (existing_email_sent and not settings.enable_napcat_service)
    ):
        print_fn("当天晚间通知已成功发送，跳过重复发送")
        return 0

    retry_pending_napcat_only = existing_email_sent and not existing_napcat_sent
    if retry_pending_napcat_only:
        summary_path = Path(str(existing.get("summary_path", "")))
        if summary_path.exists():
            markdown = summary_path.read_text(encoding="utf-8")
            notice_urls = existing.get("notice_urls", [])
            if not isinstance(notice_urls, list):
                notice_urls = []
            subject = build_email_subject_fn(settings.target_source, target_date, "evening")
            print_fn(
                f"[NEWS_TRACE] evening_retry_napcat_only subject={subject!r} output={str(summary_path)!r}"
            )
            napcat_targets = [
                str(item.get("target", ""))
                for item in existing.get("napcat_target_results", [])
                if isinstance(item, dict) and not bool(item.get("sent"))
            ]
            print_fn("当天晚间邮件已成功发送，跳过重复发送")
            napcat_sent, napcat_error, napcat_target_results = (
                _send_evening_napcat_notifications(
                    settings,
                    markdown,
                    [],
                    napcat_targets or settings.napcat_targets,
                    send_napcat_message_fn=send_napcat_message_fn,
                    build_napcat_news_message_fn=build_napcat_news_message_fn,
                    print_fn=print_fn,
                )
            )
            status = "sent" if existing_email_sent or napcat_sent else "failed"
            save_delivery_record_fn(
                store,
                target_date,
                "evening",
                summary_path,
                notice_urls,
                existing_email_sent,
                status,
                warning_emitted=not (existing_email_sent or napcat_sent),
                now=now,
                napcat_sent=napcat_sent,
                napcat_error=napcat_error,
                napcat_target_results=napcat_target_results,
            )
            print_fn(f"\n已写入: {summary_path}")
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
    print_fn(
        f"[NEWS_TRACE] evening_send subject={subject!r} notices={len(notice_urls)} output={str(evening_output)!r}"
    )

    email_sent = existing_email_sent
    napcat_sent = False
    napcat_error = ""
    napcat_target_results: list[dict[str, object]] = []

    if existing_email_sent:
        print_fn("当天晚间邮件已成功发送，跳过重复发送")
    else:
        try:
            send_email_fn(settings, subject, body, html)
            email_sent = True
            print_fn(f"邮件已发送到: {settings.email_to}")
        except (ValueError, RuntimeError, smtplib.SMTPException, OSError) as exc:
            print_fn(f"[WARN] 邮件发送失败: {exc}")

    napcat_targets = settings.napcat_targets
    if retry_pending_napcat_only:
        failed_targets = [
            str(item.get("target", ""))
            for item in existing.get("napcat_target_results", [])
            if isinstance(item, dict) and not bool(item.get("sent"))
        ]
        napcat_targets = failed_targets or settings.napcat_targets

    napcat_sent, napcat_error, napcat_target_results = (
        _send_evening_napcat_notifications(
            settings,
            markdown,
            _items,
            napcat_targets,
            send_napcat_message_fn=send_napcat_message_fn,
            build_napcat_news_message_fn=build_napcat_news_message_fn,
            print_fn=print_fn,
        )
    )

    status = "sent" if email_sent or napcat_sent else "failed"
    save_delivery_record_fn(
        store,
        target_date,
        "evening",
        evening_output,
        notice_urls,
        email_sent,
        status,
        warning_emitted=not (email_sent or napcat_sent),
        now=now,
        napcat_sent=napcat_sent,
        napcat_error=napcat_error,
        napcat_target_results=napcat_target_results,
    )

    print_fn(f"\n已写入: {evening_output}")
    return 0
