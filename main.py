import argparse
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.healthcheck import run_healthcheck
from app.runtime import Runtime, build_runtime as build_app_runtime
from app.workflows import run_daily_workflow
from backfill import build_backfill_markdown
from config import Settings
from course_client import CourseClient
from course_parser import CourseTask
from crawler import build_list_page_urls, extract_main_content, fetch_html
from delivery_state import (
    DeliveryRecord,
    DeliveryStateStore,
    get_course_task_slot,
    get_state_path,
)
from email_sender import (
    build_backfill_html,
    build_backfill_subject,
    build_course_task_email_body,
    build_course_task_email_html,
    build_course_task_email_subject,
    build_email_body,
    build_email_html,
    build_email_subject,
    send_email,
)
from models import NoticeItem
from parser import filter_recent_notices, filter_source_notices, parse_list_page
from services.backfill_service import send_backfill_if_needed as run_backfill_service
from services.cleanup_service import cleanup_old_delivery_data as run_cleanup_service
from services.course_service import (
    fetch_course_tasks as fetch_course_tasks_service,
    get_course_task_artifact_path as get_course_task_artifact_path_service,
    process_course_task_delivery as process_course_task_delivery_service,
    send_course_task_email as send_course_task_email_service,
    write_course_task_artifact as write_course_task_artifact_service,
)
from services.news_service import (
    process_evening_delivery as process_evening_delivery_service,
    process_news_delivery_safely as process_news_delivery_safely_service,
    process_noon_delivery as process_noon_delivery_service,
)
from summarizer import summarize_with_deepseek


def write_summary_file(
    text: str,
    output_dir: str = "output",
    when: datetime | None = None,
    slot: str = "noon",
) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = get_summary_file_path_for_date(output_dir, when, slot)
    path.write_text(text, encoding="utf-8")
    return path


def get_summary_file_path_for_date(
    output_dir: str = "output", when: datetime | None = None, slot: str = "noon"
) -> Path:
    ts = when or datetime.now()
    if slot == "evening":
        return Path(output_dir) / f"summary_{ts:%Y%m%d}_evening.md"
    return Path(output_dir) / f"summary_{ts:%Y%m%d}.md"


def format_summary_markdown(
    summary: str, notices: list[NoticeItem], target_source: str
) -> str:
    lines = [
        f"# {target_source}最近三天通知总结",
        "",
        "## 摘要",
        "",
        summary.strip(),
        "",
    ]
    if notices:
        lines.extend(["## 涉及通知", ""])
        for item in notices:
            lines.append(f"- `{item.publish_time:%Y-%m-%d}` [{item.title}]({item.url})")
    return "\n".join(lines).strip() + "\n"


def enrich_notice_content(notices: list[NoticeItem], timeout: int) -> list[NoticeItem]:
    enriched: list[NoticeItem] = []
    for item in notices:
        try:
            html = fetch_html(item.url, timeout=timeout)
            content = extract_main_content(html)
            item.content = content
        except RuntimeError as exc:
            print(f"[WARN] 详情抓取失败: {item.url} ({exc})")
        enriched.append(item)
    return enriched


def collect_recent_notices(settings: Settings) -> list[NoticeItem]:
    source_filtered = collect_source_notices(settings)
    recent = filter_recent_notices(source_filtered, datetime.now(), hours=72)
    recent.sort(key=lambda x: x.publish_time, reverse=True)
    return recent


def collect_source_notices(settings: Settings) -> list[NoticeItem]:
    notices: list[NoticeItem] = []
    for page_url in build_list_page_urls(settings.list_url, settings.max_pages):
        html = fetch_html(page_url, timeout=settings.request_timeout)
        notices.extend(parse_list_page(html, settings.list_url))

    deduped: dict[str, NoticeItem] = {}
    for item in notices:
        deduped[item.url] = item

    source_filtered = filter_source_notices(
        list(deduped.values()), settings.target_source
    )
    source_filtered.sort(key=lambda x: x.publish_time, reverse=True)
    return source_filtered


def fetch_course_tasks(settings: Settings) -> list[CourseTask]:
    return fetch_course_tasks_service(settings, course_client_factory=CourseClient)


def send_course_task_email(
    settings: Settings, target_date: datetime, slot: str
) -> tuple[str, str, str]:
    return send_course_task_email_service(
        settings,
        target_date,
        slot,
        fetch_course_tasks_fn=fetch_course_tasks,
        build_course_task_email_subject_fn=build_course_task_email_subject,
        build_course_task_email_body_fn=build_course_task_email_body,
        build_course_task_email_html_fn=build_course_task_email_html,
        send_email_fn=send_email,
    )


def process_course_task_delivery(
    settings: Settings, store: DeliveryStateStore, target_date: datetime, slot: str
) -> None:
    process_course_task_delivery_service(
        settings,
        store,
        target_date,
        slot,
        get_course_task_slot_fn=get_course_task_slot,
        get_course_task_artifact_path_fn=get_course_task_artifact_path_service,
        send_course_task_email_fn=send_course_task_email,
        write_course_task_artifact_fn=write_course_task_artifact_service,
        save_delivery_record_fn=save_delivery_record,
    )


def process_news_delivery_safely(
    settings: Settings, store: DeliveryStateStore, now: datetime, slot: str
) -> None:
    process_news_delivery_safely_service(
        settings,
        store,
        now,
        slot,
        process_noon_delivery_fn=process_noon_delivery,
        process_evening_delivery_fn=process_evening_delivery,
        save_delivery_record_fn=save_delivery_record,
        get_summary_file_path_for_date_fn=get_summary_file_path_for_date,
    )


def get_current_time(settings: Settings) -> datetime:
    return datetime.now(ZoneInfo(settings.schedule_timezone))


def get_current_delivery_slot(
    now: datetime,
    noon_hour: int,
    noon_minute: int,
    evening_hour: int,
    evening_minute: int,
) -> str | None:
    current = (now.hour, now.minute)
    if current == (evening_hour, evening_minute):
        return "evening"
    if current == (noon_hour, noon_minute):
        return "noon"
    return None


def get_target_delivery_date(
    now: datetime, schedule_hour: int, schedule_minute: int = 0
) -> datetime:
    if (now.hour, now.minute) < (schedule_hour, schedule_minute):
        return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=1
        )
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_notice_urls(notices: list[NoticeItem]) -> list[str]:
    return sorted({item.url for item in notices})


def collect_notices_for_date(
    settings: Settings, target_date: datetime
) -> list[NoticeItem]:
    source_filtered = collect_source_notices(settings)
    filtered = [
        item
        for item in source_filtered
        if item.publish_time.date() == target_date.date()
    ]
    filtered.sort(key=lambda x: x.publish_time, reverse=True)
    return filtered


def trim_notices_to_cutoff(
    notices: list[NoticeItem],
    target_date: datetime,
    cutoff_hour: int,
    cutoff_minute: int,
) -> list[NoticeItem]:
    cutoff = target_date.replace(hour=cutoff_hour, minute=cutoff_minute)
    cutoff_naive = cutoff.replace(tzinfo=None)
    return [
        item
        for item in notices
        if item.publish_time.replace(tzinfo=None) <= cutoff_naive
    ]


def build_notice_outputs(
    settings: Settings,
    notices: list[NoticeItem],
    target_date: datetime,
    slot: str = "noon",
) -> tuple[str, str, str, list[NoticeItem], list[str]]:
    if not notices:
        summary = format_summary_markdown(
            "最近三天没有通知。", [], settings.target_source
        )
        body = build_email_body("最近三天没有通知。", [], settings.target_source)
        html = build_email_html(
            "最近三天没有通知。", [], settings.target_source, slot=slot
        )
        return summary, body, html, [], []

    full_items = enrich_notice_content(notices, timeout=settings.request_timeout)
    summary = summarize_with_deepseek(full_items, settings)
    markdown = format_summary_markdown(summary, full_items, settings.target_source)
    body = build_email_body(summary, full_items, settings.target_source)
    html = build_email_html(summary, full_items, settings.target_source, slot=slot)
    return markdown, body, html, full_items, get_notice_urls(full_items)


def save_delivery_record(
    store: DeliveryStateStore,
    target_date: datetime,
    slot: str,
    summary_path: Path,
    notice_urls: list[str],
    email_sent: bool,
    status: str,
    warning_emitted: bool = False,
    backfilled: bool = False,
    now: datetime | None = None,
) -> None:
    timestamp = (now or datetime.now()).isoformat()
    sent_at = timestamp if email_sent else ""
    store.record(
        DeliveryRecord(
            date=target_date.date().isoformat(),
            slot=slot,
            summary_path=str(summary_path),
            email_sent=email_sent,
            notice_urls=notice_urls,
            status=status,
            warning_emitted=warning_emitted,
            sent_at=sent_at,
            updated_at=timestamp,
            backfilled=backfilled,
        )
    )


def cleanup_old_delivery_data(
    settings: Settings, store: DeliveryStateStore, now: datetime
) -> None:
    run_cleanup_service(settings, store, now)


def send_backfill_if_needed(
    settings: Settings,
    store: DeliveryStateStore,
    now: datetime,
    include_today: bool,
) -> None:
    run_backfill_service(
        settings,
        store,
        now,
        include_today,
        collect_notices_for_date_fn=collect_notices_for_date,
        trim_notices_to_cutoff_fn=trim_notices_to_cutoff,
        build_notice_outputs_fn=build_notice_outputs,
        write_summary_file_fn=write_summary_file,
        build_backfill_markdown_fn=build_backfill_markdown,
        build_backfill_subject_fn=build_backfill_subject,
        build_backfill_html_fn=build_backfill_html,
        send_email_fn=send_email,
        save_delivery_record_fn=save_delivery_record,
    )


def process_noon_delivery(
    settings: Settings, store: DeliveryStateStore, now: datetime
) -> int:
    return process_noon_delivery_service(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=get_summary_file_path_for_date,
        collect_notices_for_date_fn=collect_notices_for_date,
        trim_notices_to_cutoff_fn=trim_notices_to_cutoff,
        build_notice_outputs_fn=build_notice_outputs,
        write_summary_file_fn=write_summary_file,
        build_email_subject_fn=build_email_subject,
        send_email_fn=send_email,
        save_delivery_record_fn=save_delivery_record,
    )


def process_evening_delivery(
    settings: Settings, store: DeliveryStateStore, now: datetime
) -> int:
    return process_evening_delivery_service(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=get_summary_file_path_for_date,
        collect_notices_for_date_fn=collect_notices_for_date,
        build_notice_outputs_fn=build_notice_outputs,
        write_summary_file_fn=write_summary_file,
        build_email_subject_fn=build_email_subject,
        send_email_fn=send_email,
        save_delivery_record_fn=save_delivery_record,
    )


def retry_failed_deliveries_for_today(
    settings: Settings, store: DeliveryStateStore, now: datetime
) -> set[str]:
    attempted: set[str] = set()
    today = now.date().isoformat()
    noon = store.get_record(today, "noon")
    if noon and noon.get("status") == "failed" and not bool(noon.get("email_sent")):
        attempted.add("noon")
        process_noon_delivery(settings, store, now)

    evening = store.get_record(today, "evening")
    if (
        evening
        and evening.get("status") == "failed"
        and not bool(evening.get("email_sent"))
    ):
        attempted.add("evening")
        process_evening_delivery(settings, store, now)

    return attempted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("run", "news", "healthcheck"), default="run")
    return parser.parse_args()


def run_news_mode(runtime: Runtime | None = None) -> int:
    if runtime is None:
        return run()
    return run_daily_workflow(runtime)


def process_course_run(runtime: Runtime) -> None:
    target_date = runtime.now.replace(hour=0, minute=0, second=0, microsecond=0)
    course_task_slot = runtime.run_slot or "manual"
    process_course_task_delivery(
        runtime.settings,
        runtime.store,
        target_date,
        course_task_slot,
    )


def process_news_run(runtime: Runtime) -> None:
    if runtime.run_slot == "noon":
        if "noon" in runtime.retried_slots:
            return
        process_news_delivery_safely(
            runtime.settings, runtime.store, runtime.now, "noon"
        )
        return
    if runtime.run_slot == "evening":
        if "evening" in runtime.retried_slots:
            return
        process_news_delivery_safely(
            runtime.settings, runtime.store, runtime.now, "evening"
        )


def build_runtime(
    settings_loader: Callable[[], Settings] = Settings.from_env,
) -> Runtime:
    return build_app_runtime(
        settings_loader=settings_loader,
        store_factory=DeliveryStateStore,
        state_path_builder=get_state_path,
        clock=get_current_time,
        cleanup_old_delivery_data=cleanup_old_delivery_data,
        retry_failed_deliveries_for_today=retry_failed_deliveries_for_today,
        get_current_delivery_slot=get_current_delivery_slot,
        send_backfill_if_needed=send_backfill_if_needed,
        process_course_run=process_course_run,
        process_news_run=process_news_run,
    )


def load_settings_for_mode(mode: str) -> Settings:
    settings = Settings.from_env(validate=mode != "healthcheck")
    Settings.validate_for_mode(settings, mode)
    return settings


def main() -> int:
    args = parse_args()
    if args.mode == "healthcheck":
        try:
            settings = load_settings_for_mode("healthcheck")
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            return 1
        return run_healthcheck(settings)
    try:
        settings = load_settings_for_mode(args.mode)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1
    runtime = build_runtime(settings_loader=lambda: settings)
    if args.mode == "news":
        return run_news_mode(runtime)
    return run_daily_workflow(runtime)


def run() -> int:
    try:
        settings = load_settings_for_mode("run")
        runtime = build_runtime(settings_loader=lambda: settings)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1
    return run_daily_workflow(runtime)


if __name__ == "__main__":
    raise SystemExit(main())
