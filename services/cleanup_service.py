from datetime import datetime

from config import Settings
from delivery_state import DeliveryStateStore


def cleanup_old_delivery_data(
    settings: Settings, store: DeliveryStateStore, now: datetime
) -> None:
    store.cleanup(now, settings.state_retention_days)
