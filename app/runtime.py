from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import Settings
from delivery_state import DeliveryStateStore


@dataclass(slots=True)
class Runtime:
    settings: Settings
    store: DeliveryStateStore
    now: datetime
    run_slot: str | None
    retried_slots: set[str]
    cleanup_old_delivery_data: Callable[[Settings, DeliveryStateStore, datetime], None]
    retry_failed_deliveries_for_today: Callable[
        [Settings, DeliveryStateStore, datetime], set[str]
    ]
    get_current_delivery_slot: Callable[[datetime, int, int, int, int], str | None]
    send_backfill_if_needed: Callable[
        [Settings, DeliveryStateStore, datetime, bool], None
    ]
    process_course_run: Callable[["Runtime"], None]
    process_news_run: Callable[["Runtime"], None]


def build_runtime(
    *,
    settings_loader: Callable[[], Settings],
    store_factory: Callable[[Path], DeliveryStateStore],
    state_path_builder: Callable[[str], Path],
    clock: Callable[[Settings], datetime],
    cleanup_old_delivery_data: Callable[[Settings, DeliveryStateStore, datetime], None],
    retry_failed_deliveries_for_today: Callable[
        [Settings, DeliveryStateStore, datetime], set[str]
    ],
    get_current_delivery_slot: Callable[[datetime, int, int, int, int], str | None],
    send_backfill_if_needed: Callable[
        [Settings, DeliveryStateStore, datetime, bool], None
    ],
    process_course_run: Callable[[Runtime], None],
    process_news_run: Callable[[Runtime], None],
) -> Runtime:
    settings = settings_loader()
    store = store_factory(state_path_builder(settings.output_dir))
    now = clock(settings)
    return Runtime(
        settings=settings,
        store=store,
        now=now,
        run_slot=None,
        retried_slots=set(),
        cleanup_old_delivery_data=cleanup_old_delivery_data,
        retry_failed_deliveries_for_today=retry_failed_deliveries_for_today,
        get_current_delivery_slot=get_current_delivery_slot,
        send_backfill_if_needed=send_backfill_if_needed,
        process_course_run=process_course_run,
        process_news_run=process_news_run,
    )
