from datetime import date, datetime
from zoneinfo import ZoneInfo

from delivery_state import DeliveryRecord, DeliveryStateStore, get_course_task_slot


def test_record_delivery_status_persists_slot_success(tmp_path):
    state = DeliveryStateStore(tmp_path / "state.json")
    state.record(
        DeliveryRecord(
            date="2026-03-19",
            slot="noon",
            summary_path="output/summary_20260319.md",
            email_sent=False,
            notice_urls=["http://example.com/a"],
            status="failed",
        )
    )
    loaded = state.list_records()
    assert loaded[0]["slot"] == "noon"
    assert loaded[0]["email_sent"] is False


def test_missing_noon_dates_detects_unsent_days(tmp_path):
    state = DeliveryStateStore(tmp_path / "state.json")
    state.record(
        DeliveryRecord(
            date="2026-03-18",
            slot="noon",
            summary_path="output/summary_20260318.md",
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )
    missing = state.missing_noon_dates(date(2026, 3, 19), 3, include_end_date=False)
    assert missing == [date(2026, 3, 17)]


def test_get_course_task_slot_names_course_task_delivery_slots():
    assert get_course_task_slot("noon") == "course_tasks_noon"
    assert get_course_task_slot("evening") == "course_tasks_evening"


def test_cleanup_removes_state_older_than_retention_window(tmp_path):
    state = DeliveryStateStore(tmp_path / "state.json")
    state.record(
        DeliveryRecord(
            date="2026-02-01",
            slot="noon",
            summary_path="old.md",
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )
    state.record(
        DeliveryRecord(
            date="2026-03-18",
            slot="noon",
            summary_path="new.md",
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )
    changed = state.cleanup(datetime(2026, 3, 19, 12, 0), 15)
    records = state.list_records()
    assert changed is True
    assert len(records) == 1
    assert records[0]["date"] == "2026-03-18"


def test_cleanup_skips_when_recently_cleaned(tmp_path):
    state = DeliveryStateStore(tmp_path / "state.json")
    state.save({"meta": {"last_cleanup_at": "2026-03-18T12:00:00"}, "records": []})
    changed = state.cleanup(datetime(2026, 3, 19, 12, 0), 15)
    assert changed is False


def test_load_returns_empty_state_for_corrupted_json(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{broken", encoding="utf-8")
    state = DeliveryStateStore(path)
    assert state.load() == {"meta": {"last_cleanup_at": ""}, "records": []}


def test_cleanup_handles_invalid_last_cleanup_timestamp(tmp_path):
    state = DeliveryStateStore(tmp_path / "state.json")
    state.save({"meta": {"last_cleanup_at": "not-a-date"}, "records": []})
    changed = state.cleanup(datetime(2026, 3, 19, 12, 0), 15)
    assert changed is True


def test_cleanup_handles_aware_now_with_legacy_naive_last_cleanup_at(tmp_path):
    state = DeliveryStateStore(tmp_path / "state.json")
    state.save({"meta": {"last_cleanup_at": "2026-03-18T12:00:00"}, "records": []})
    changed = state.cleanup(
        datetime(2026, 3, 19, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")), 15
    )
    assert changed is False
