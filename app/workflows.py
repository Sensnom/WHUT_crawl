from app.runtime import Runtime


def run_daily_workflow(runtime: Runtime) -> int:
    runtime.cleanup_old_delivery_data(runtime.settings, runtime.store, runtime.now)
    retried_slots: set[str] = set()
    if runtime.settings.enable_news_service:
        retried_slots = runtime.retry_failed_deliveries_for_today(
            runtime.settings, runtime.store, runtime.now
        )
    slot = runtime.get_current_delivery_slot(
        runtime.now,
        runtime.settings.schedule_hour,
        runtime.settings.schedule_minute,
        runtime.settings.evening_schedule_hour,
        runtime.settings.evening_schedule_minute,
    )

    if runtime.settings.enable_news_service:
        runtime.send_backfill_if_needed(
            runtime.settings, runtime.store, runtime.now, slot == "evening"
        )
    runtime.run_slot = slot
    runtime.retried_slots = retried_slots

    if runtime.settings.enable_course_service:
        runtime.process_course_run(runtime)
    if runtime.settings.enable_news_service:
        runtime.process_news_run(runtime)

    if slot in {"noon", "evening"}:
        return 0

    if runtime.settings.enable_news_service and runtime.settings.enable_course_service:
        print("当前时间不在 12:00 或 18:00 发送窗口，新闻摘要跳过，课程任务照常发送")
    elif runtime.settings.enable_news_service:
        print("当前时间不在 12:00 或 18:00 发送窗口，新闻摘要跳过")
    elif runtime.settings.enable_course_service:
        print("当前时间不在 12:00 或 18:00 发送窗口，仅课程任务服务开启")
    return 0
