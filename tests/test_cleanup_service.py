from datetime import datetime
from pathlib import Path

from config import Settings
from delivery_state import DeliveryStateStore
from services.cleanup_service import cleanup_old_delivery_data


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
        backfill_max_days=2,
        state_retention_days=15,
    )


def test_cleanup_old_delivery_data_no_longer_touches_legacy_cron_log(tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    log_path = tmp_path / "cron.log"
    log_path.write_text(
        "".join(f"line-{index}\n" for index in range(1105)), encoding="utf-8"
    )

    cleanup_old_delivery_data(settings, store, datetime(2026, 3, 20, 12, 0))

    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1105


def test_cleanup_old_delivery_data_leaves_legacy_log_untouched_when_store_skips_cleanup(
    tmp_path: Path,
):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 12, 0)
    store.save({"meta": {"last_cleanup_at": now.isoformat()}, "records": []})
    log_path = tmp_path / "cron.log"
    original = "line-1\nline-2\n"
    log_path.write_text(original, encoding="utf-8")

    cleanup_old_delivery_data(settings, store, now)

    assert log_path.read_text(encoding="utf-8") == original
