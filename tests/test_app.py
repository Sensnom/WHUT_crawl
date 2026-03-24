from datetime import datetime
from pathlib import Path

from app.runtime import Runtime, build_runtime
from app.workflows import run_daily_workflow
from config import Settings
from delivery_state import DeliveryStateStore


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


def test_build_runtime_wires_dependencies(tmp_path: Path):
    settings = make_settings(tmp_path)
    expected_now = datetime(2026, 3, 20, 12, 0)
    expected_path = tmp_path / "state.json"
    expected_store = DeliveryStateStore(expected_path)
    called = {}

    def settings_loader():
        called["settings_loader"] = True
        return settings

    def state_path_builder(output_dir: str) -> Path:
        called["output_dir"] = output_dir
        return expected_path

    def store_factory(path: Path) -> DeliveryStateStore:
        called["store_path"] = path
        return expected_store

    def clock(received_settings: Settings) -> datetime:
        called["clock_settings"] = received_settings
        return expected_now

    cleanup = lambda *_args: None
    retry = lambda *_args: set()
    get_slot = lambda *_args: None
    send_backfill = lambda *_args, **_kwargs: None
    process_course = lambda _runtime: None
    process_news = lambda _runtime: None

    runtime = build_runtime(
        settings_loader=settings_loader,
        store_factory=store_factory,
        state_path_builder=state_path_builder,
        clock=clock,
        cleanup_old_delivery_data=cleanup,
        retry_failed_deliveries_for_today=retry,
        get_current_delivery_slot=get_slot,
        send_backfill_if_needed=send_backfill,
        process_course_run=process_course,
        process_news_run=process_news,
    )

    assert called == {
        "settings_loader": True,
        "output_dir": str(tmp_path),
        "store_path": expected_path,
        "clock_settings": settings,
    }
    assert runtime.settings is settings
    assert runtime.store is expected_store
    assert runtime.now == expected_now
    assert runtime.run_slot is None
    assert runtime.retried_slots == set()
    assert runtime.cleanup_old_delivery_data is cleanup
    assert runtime.retry_failed_deliveries_for_today is retry
    assert runtime.get_current_delivery_slot is get_slot
    assert runtime.send_backfill_if_needed is send_backfill
    assert runtime.process_course_run is process_course
    assert runtime.process_news_run is process_news


def test_run_daily_workflow_executes_runtime_steps_for_noon_slot(tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "email_delivery_state.json")
    now = datetime(2026, 3, 20, 12, 0, 45)
    calls: list[tuple[object, ...]] = []

    def cleanup(received_settings, received_store, received_now):
        calls.append(("cleanup", received_settings, received_store, received_now))

    def retry(received_settings, received_store, received_now):
        calls.append(("retry", received_settings, received_store, received_now))
        return set()

    def get_slot(
        received_now, noon_hour, noon_minute, evening_hour, evening_minute
    ) -> str:
        calls.append(
            ("slot", received_now, noon_hour, noon_minute, evening_hour, evening_minute)
        )
        return "noon"

    def send_backfill(received_settings, received_store, received_now, include_today):
        calls.append(
            ("backfill", received_settings, received_store, received_now, include_today)
        )

    def process_course(runtime: Runtime):
        calls.append(
            (
                "course",
                runtime.settings,
                runtime.store,
                runtime.now.replace(hour=0, minute=0, second=0, microsecond=0),
                runtime.run_slot,
            )
        )

    def process_news(runtime: Runtime):
        calls.append(
            ("news", runtime.settings, runtime.store, runtime.now, runtime.run_slot)
        )

    runtime = Runtime(
        settings=settings,
        store=store,
        now=now,
        run_slot=None,
        retried_slots=set(),
        cleanup_old_delivery_data=cleanup,
        retry_failed_deliveries_for_today=retry,
        get_current_delivery_slot=get_slot,
        send_backfill_if_needed=send_backfill,
        process_course_run=process_course,
        process_news_run=process_news,
    )

    assert run_daily_workflow(runtime) == 0
    assert calls == [
        ("cleanup", settings, store, now),
        ("retry", settings, store, now),
        ("slot", now, 12, 0, 18, 0),
        ("backfill", settings, store, now, False),
        (
            "course",
            settings,
            store,
            datetime(2026, 3, 20, 0, 0),
            "noon",
        ),
        ("news", settings, store, now, "noon"),
    ]
