# Twice-Daily Email And Backfill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a noon-and-evening delivery workflow with slot-based delivery state, conditional 18:00 sending for new notices only, aggregated backfill for up to 7 missed days, and periodic cleanup of logs and state.

**Architecture:** Keep `main.py` as the entrypoint but move delivery tracking into a dedicated state module keyed by date and slot. Add explicit regular-delivery and backfill-building helpers so noon/evening logic, retry decisions, and cleanup behavior remain testable and separate from crawling and email transport.

**Tech Stack:** Python 3, json, datetime/zoneinfo stdlib, pathlib, python-dotenv, pytest

---

### Task 1: Add slot and retention configuration

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_settings_reads_evening_and_retention_fields(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("EVENING_SCHEDULE_HOUR", "18")
    monkeypatch.setenv("EVENING_SCHEDULE_MINUTE", "0")
    monkeypatch.setenv("BACKFILL_MAX_DAYS", "7")
    monkeypatch.setenv("STATE_RETENTION_DAYS", "15")
    settings = Settings.from_env()
    assert settings.evening_schedule_hour == 18
    assert settings.backfill_max_days == 7
    assert settings.state_retention_days == 15
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_reads_evening_and_retention_fields -v`
Expected: FAIL because these config fields do not exist yet.

**Step 3: Write minimal implementation**

Add evening slot and retention settings to `Settings`, load them from `.env`, and document defaults in `.env.example`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_settings_reads_evening_and_retention_fields -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add config.py .env.example tests/test_config.py
git commit -m "feat: add twice-daily delivery configuration"
```

### Task 2: Add delivery state storage and cleanup

**Files:**
- Create: `delivery_state.py`
- Create: `tests/test_delivery_state.py`

**Step 1: Write the failing test**

```python
def test_record_delivery_status_persists_slot_success(tmp_path):
    state = DeliveryStateStore(tmp_path / "state.json")
    state.record(
        date="2026-03-19",
        slot="noon",
        summary_path="output/summary_20260319.md",
        email_sent=False,
        notice_urls=["http://example.com/a"],
    )
    loaded = state.load()
    assert loaded[0]["slot"] == "noon"
    assert loaded[0]["email_sent"] is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_delivery_state.py::test_record_delivery_status_persists_slot_success -v`
Expected: FAIL because the module does not exist.

**Step 3: Write minimal implementation**

Create a small JSON-backed state store with read/write helpers, slot records, and a cleanup method that drops entries older than the retention window.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_delivery_state.py::test_record_delivery_status_persists_slot_success -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add delivery_state.py tests/test_delivery_state.py
git commit -m "feat: store slot-based email delivery state"
```

### Task 3: Detect missing days and build aggregated backfill files

**Files:**
- Create: `backfill.py`
- Modify: `email_sender.py`
- Create: `tests/test_backfill.py`
- Modify: `tests/test_email_sender.py`

**Step 1: Write the failing test**

```python
def test_build_backfill_markdown_groups_missing_days_and_uses_bufa_name(tmp_path):
    path, body = build_backfill_markdown(
        output_dir=tmp_path,
        date_sections={
            "2026-03-12": "# 2026-03-12\n内容A",
            "2026-03-14": "# 2026-03-14\n内容B",
        },
    )
    assert "补发" in path.name
    assert "2026-03-12" in body
    assert "2026-03-14" in body
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_backfill.py::test_build_backfill_markdown_groups_missing_days_and_uses_bufa_name -v`
Expected: FAIL because the module does not exist.

**Step 3: Write minimal implementation**

Add helpers that accept per-day content, write one aggregated `补发_summary_*.md`, and format a matching backfill email subject/body.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_backfill.py::test_build_backfill_markdown_groups_missing_days_and_uses_bufa_name -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backfill.py email_sender.py tests/test_backfill.py tests/test_email_sender.py
git commit -m "feat: build aggregated backfill emails"
```

### Task 4: Implement noon and evening slot selection

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_get_current_delivery_slot_returns_evening_after_18(monkeypatch):
    slot = get_current_delivery_slot(datetime(2026, 3, 19, 18, 0), 12, 0, 18, 0)
    assert slot == "evening"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_get_current_delivery_slot_returns_evening_after_18 -v`
Expected: FAIL because slot selection does not exist yet.

**Step 3: Write minimal implementation**

Add helpers that classify the current run as `noon`, `evening`, or `outside_delivery_window`, based on configured times.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_get_current_delivery_slot_returns_evening_after_18 -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: classify noon and evening delivery slots"
```

### Task 5: Send noon slot and record notice identities

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_delivery_state.py`

**Step 1: Write the failing test**

```python
def test_run_noon_records_sent_notice_urls(monkeypatch, tmp_path):
    ...
    assert run() == 0
    state = load_state(...)
    assert state[0]["slot"] == "noon"
    assert "http://example.com/a" in state[0]["notice_urls"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_noon_records_sent_notice_urls -v`
Expected: FAIL because noon sends do not persist slot state yet.

**Step 3: Write minimal implementation**

After a noon send attempt, record the date, slot, summary path, send result, and notice URL set in the state file.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_noon_records_sent_notice_urls -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py delivery_state.py tests/test_main.py tests/test_delivery_state.py
git commit -m "feat: persist noon delivery state"
```

### Task 6: Send evening slot only when there are new notices

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_evening_skips_when_no_new_notices(monkeypatch, tmp_path):
    ...
    assert run() == 0
    assert sent["count"] == 0


def test_run_evening_sends_when_new_notices_exist(monkeypatch, tmp_path):
    ...
    assert run() == 0
    assert sent["count"] == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_evening_skips_when_no_new_notices tests/test_main.py::test_run_evening_sends_when_new_notices_exist -v`
Expected: FAIL because evening-delta logic does not exist.

**Step 3: Write minimal implementation**

Compare the current evening notice identities against the noon record for the same date, send only the new subset, and persist an evening slot record.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_evening_skips_when_no_new_notices tests/test_main.py::test_run_evening_sends_when_new_notices_exist -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py delivery_state.py tests/test_main.py
git commit -m "feat: send evening updates only for new notices"
```

### Task 7: Aggregate and send backfill for up to 7 missed days

**Files:**
- Modify: `main.py`
- Modify: `backfill.py`
- Modify: `delivery_state.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_backfill.py`

**Step 1: Write the failing test**

```python
def test_run_sends_single_backfill_email_for_multiple_missing_days(monkeypatch, tmp_path):
    ...
    assert run() == 0
    assert sent["subject"].startswith("WHUT 本科生院通知补发")
    assert "2026-03-12" in sent["body"]
    assert "2026-03-18" in sent["body"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_sends_single_backfill_email_for_multiple_missing_days -v`
Expected: FAIL because backfill aggregation is not wired into `run()`.

**Step 3: Write minimal implementation**

When the state file shows missed days within the 7-day window, rebuild those days using their own target dates, write one `补发_summary_*.md`, send one aggregated backfill email, then mark those missed dates handled.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_sends_single_backfill_email_for_multiple_missing_days -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py backfill.py delivery_state.py tests/test_main.py tests/test_backfill.py
git commit -m "feat: aggregate missed days into one backfill email"
```

### Task 8: Add warning and resend behavior for failed email attempts

**Files:**
- Modify: `main.py`
- Modify: `delivery_state.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_delivery_state.py`

**Step 1: Write the failing test**

```python
def test_failed_email_attempt_is_marked_for_warning_and_retry(monkeypatch, tmp_path):
    ...
    assert run() == 0
    state = load_state(...)
    assert state[0]["email_sent"] is False
    assert state[0]["warning_emitted"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_failed_email_attempt_is_marked_for_warning_and_retry -v`
Expected: FAIL because failures are not tracked with warning/retry metadata.

**Step 3: Write minimal implementation**

On send failure, update state instead of pretending the date is finished; emit a warning and allow the same slot/day to be retried later.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_failed_email_attempt_is_marked_for_warning_and_retry -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py delivery_state.py tests/test_main.py tests/test_delivery_state.py
git commit -m "feat: track failed email sends for warning and retry"
```

### Task 9: Clean old logs and state every 15 days

**Files:**
- Modify: `main.py`
- Modify: `delivery_state.py`
- Create: `tests/test_cleanup.py`

**Step 1: Write the failing test**

```python
def test_cleanup_removes_state_older_than_retention_window(tmp_path):
    ...
    cleanup_old_delivery_data(...)
    assert "2026-02-01" not in remaining_dates
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cleanup.py::test_cleanup_removes_state_older_than_retention_window -v`
Expected: FAIL because cleanup logic does not exist.

**Step 3: Write minimal implementation**

Add a cleanup helper that prunes old state records and rotates/truncates old logs according to the 15-day retention policy.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cleanup.py::test_cleanup_removes_state_older_than_retention_window -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py delivery_state.py tests/test_cleanup.py
git commit -m "feat: clean old delivery state and logs"
```

### Task 10: Update cron and docs for twice-daily sends

**Files:**
- Modify: `README.md`
- Modify: `scheduler/cron.example`
- Modify: `scheduler/manage_cron.py`
- Modify: `tests/test_scheduler.py`
- Modify: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_build_managed_cron_block_contains_noon_and_evening_runs(tmp_path):
    block = build_managed_cron_block(...)
    assert "0 12 * * *" in block
    assert "0 18 * * *" in block
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py::test_build_managed_cron_block_contains_noon_and_evening_runs -v`
Expected: FAIL because cron generation still emits one entry.

**Step 3: Write minimal implementation**

Generate two cron entries, document the noon/evening behavior, explain backfill/state/cleanup, and update smoke assertions.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py tests/test_smoke.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add README.md scheduler/cron.example scheduler/manage_cron.py tests/test_scheduler.py tests/test_smoke.py
git commit -m "docs: describe twice-daily delivery and backfill"
```

### Task 11: Verify the full feature set

**Files:**
- Modify: none

**Step 1: Write the failing test**

No new automated test. Use the full suite as final regression coverage.

**Step 2: Run test to verify it fails**

Not applicable.

**Step 3: Write minimal implementation**

No code changes.

**Step 4: Run test to verify it passes**

Run: `pytest -v`
Expected: PASS.

Run: `python scheduler/manage_cron.py --print`
Expected: prints both `12:00` and `18:00` cron entries.

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add twice-daily delivery with aggregated backfill"
```
