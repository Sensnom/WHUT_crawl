from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import Any


STATE_FILENAME = "email_delivery_state.json"


def get_course_task_slot(slot: str) -> str:
    return f"course_tasks_{slot}"


@dataclass
class DeliveryRecord:
    date: str
    slot: str
    summary_path: str
    email_sent: bool
    notice_urls: list[str]
    status: str
    warning_emitted: bool = False
    sent_at: str = ""
    updated_at: str = ""
    backfilled: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "date": self.date,
            "slot": self.slot,
            "summary_path": self.summary_path,
            "email_sent": self.email_sent,
            "notice_urls": self.notice_urls,
            "status": self.status,
            "warning_emitted": self.warning_emitted,
            "sent_at": self.sent_at,
            "updated_at": self.updated_at,
            "backfilled": self.backfilled,
        }


class DeliveryStateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"meta": {"last_cleanup_at": ""}, "records": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"meta": {"last_cleanup_at": ""}, "records": []}

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

    def list_records(self) -> list[dict[str, Any]]:
        data = self.load()
        records = data.get("records", [])
        return records if isinstance(records, list) else []

    def get_record(self, record_date: str, slot: str) -> dict[str, Any] | None:
        for record in self.list_records():
            if record.get("date") == record_date and record.get("slot") == slot:
                return record
        return None

    def record(self, record: DeliveryRecord) -> None:
        data = self.load()
        records = self.list_records()
        updated = False
        for index, item in enumerate(records):
            if item.get("date") == record.date and item.get("slot") == record.slot:
                records[index] = record.to_dict()
                updated = True
                break
        if not updated:
            records.append(record.to_dict())
        data["records"] = records
        self.save(data)

    def missing_noon_dates(
        self, end_date: date, max_days: int, include_end_date: bool = True
    ) -> list[date]:
        missing: list[date] = []
        stop = 0 if include_end_date else 1
        for offset in range(max_days - 1, stop - 1, -1):
            current = end_date - timedelta(days=offset)
            record = self.get_record(current.isoformat(), "noon")
            if not record or not bool(record.get("email_sent")):
                missing.append(current)
        return missing

    def cleanup(self, now: datetime, retention_days: int) -> bool:
        data = self.load()
        meta = data.get("meta", {})
        if not isinstance(meta, dict):
            meta = {}
        last_cleanup_at = str(meta.get("last_cleanup_at", ""))
        if last_cleanup_at:
            try:
                previous = datetime.fromisoformat(last_cleanup_at)
            except ValueError:
                previous = None
            if (
                previous is not None
                and previous.tzinfo is None
                and now.tzinfo is not None
            ):
                previous = previous.replace(tzinfo=now.tzinfo)
            if previous is not None and now - previous < timedelta(days=retention_days):
                return False

        cutoff = now.date() - timedelta(days=retention_days)
        kept = []
        for record in self.list_records():
            try:
                record_date = date.fromisoformat(str(record.get("date", "")))
            except ValueError:
                continue
            if record_date >= cutoff:
                kept.append(record)

        meta["last_cleanup_at"] = now.isoformat()
        data["meta"] = meta
        data["records"] = kept
        self.save(data)
        return True


def get_state_path(output_dir: str) -> Path:
    return Path(output_dir) / STATE_FILENAME
