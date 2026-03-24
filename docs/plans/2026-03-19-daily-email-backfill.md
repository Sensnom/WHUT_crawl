# Daily Email Backfill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Change daily email delivery to noon and add a simplified missed-send backfill rule that sends only the most recent missing date based on whether that date's summary file exists.

**Architecture:** Keep `main.py` as the only runtime entrypoint, but compute a target delivery date from the current time and the configured schedule hour. Treat `output/summary_YYYYMMDD.md` as the single source of truth for whether a date has already been handled, then reuse or generate the summary for that date and send one email at most.

**Tech Stack:** Python 3, datetime stdlib, pathlib, python-dotenv, pytest

---

### Task 1: Change default schedule to noon

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_settings_uses_noon_schedule_by_default(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("SCHEDULE_HOUR", raising=False)
    settings = Settings.from_env()
    assert settings.schedule_hour == 12
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_uses_noon_schedule_by_default -v`
Expected: FAIL because the default schedule hour is still `8`.

**Step 3: Write minimal implementation**

Update the default schedule hour in `config.py` and `.env.example` from `8` to `12`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_settings_uses_noon_schedule_by_default -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add config.py .env.example tests/test_config.py
git commit -m "feat: change daily email default schedule to noon"
```

### Task 2: Add target delivery date helpers

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_get_target_delivery_date_before_noon_uses_previous_day():
    result = get_target_delivery_date(datetime(2026, 3, 19, 11, 0), 12)
    assert result.date().isoformat() == "2026-03-18"


def test_get_target_delivery_date_after_noon_uses_today():
    result = get_target_delivery_date(datetime(2026, 3, 19, 12, 1), 12)
    assert result.date().isoformat() == "2026-03-19"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_get_target_delivery_date_before_noon_uses_previous_day tests/test_main.py::test_get_target_delivery_date_after_noon_uses_today -v`
Expected: FAIL because the helper does not exist.

**Step 3: Write minimal implementation**

Add a helper that takes `now` and `schedule_hour`, and returns yesterday when current time is before the schedule hour, otherwise today.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_get_target_delivery_date_before_noon_uses_previous_day tests/test_main.py::test_get_target_delivery_date_after_noon_uses_today -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: compute target delivery date for daily email"
```

### Task 3: Support summary paths for explicit dates

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_get_summary_file_path_for_date_supports_explicit_delivery_day(tmp_path):
    path = get_summary_file_path_for_date(
        str(tmp_path),
        datetime(2026, 3, 18, 12, 0),
    )
    assert path == tmp_path / "summary_20260318.md"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_get_summary_file_path_for_date_supports_explicit_delivery_day -v`
Expected: PASS already or trivial adjustment needed; if already covered, replace with a test for `write_summary_file(..., when=...)` that fails first.

**Step 3: Write minimal implementation**

If needed, extend `write_summary_file` to accept an explicit target datetime so the pipeline can write yesterday's summary file during backfill.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_get_summary_file_path_for_date_supports_explicit_delivery_day -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "refactor: support explicit delivery dates for summary files"
```

### Task 4: Skip processing when target date file already exists

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_skips_when_target_delivery_file_already_exists(monkeypatch, tmp_path):
    target = tmp_path / "summary_20260318.md"
    target.write_text("done", encoding="utf-8")
    called = {"collect": 0, "send": 0}
    ...
    assert run() == 0
    assert called["collect"] == 0
    assert called["send"] == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_skips_when_target_delivery_file_already_exists -v`
Expected: FAIL because current logic still tries to send when a file exists.

**Step 3: Write minimal implementation**

Change `run()` so it computes the target delivery date first and exits early when that date's summary file already exists.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_skips_when_target_delivery_file_already_exists -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: skip already handled delivery dates"
```

### Task 5: Generate and send the most recent missing date

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_backfills_previous_day_before_noon(monkeypatch, tmp_path):
    settings = Settings(..., output_dir=str(tmp_path), schedule_hour=12)
    monkeypatch.setattr("main.Settings.from_env", lambda: settings)
    monkeypatch.setattr("main.datetime", FakeDatetimeReturning(2026, 3, 19, 11, 0))
    sent = {}
    ...
    assert run() == 0
    assert (tmp_path / "summary_20260318.md").exists()
    assert "2026-03-18" in sent["subject"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_backfills_previous_day_before_noon -v`
Expected: FAIL because the pipeline still targets the current date and subject.

**Step 3: Write minimal implementation**

Update `run()` to:
- compute the target delivery date
- write the summary file for that date
- build the email subject for that date
- send only one email for that target date

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_backfills_previous_day_before_noon -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: backfill the most recent missing delivery date"
```

### Task 6: Document simplified backfill behavior

**Files:**
- Modify: `README.md`
- Modify: `scheduler/cron.example`
- Test: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_readme_documents_noon_backfill_behavior():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "SCHEDULE_HOUR=12" in readme
    assert "只补最近一个缺失日期" in readme
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py::test_readme_documents_noon_backfill_behavior -v`
Expected: FAIL until docs are updated.

**Step 3: Write minimal implementation**

Update docs and cron example to show noon delivery and explain that missing sends are determined only by whether the target date summary file exists.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py::test_readme_documents_noon_backfill_behavior -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add README.md scheduler/cron.example tests/test_smoke.py
git commit -m "docs: describe noon backfill behavior"
```

### Task 7: Verify the full behavior

**Files:**
- Modify: none

**Step 1: Write the failing test**

No new automated test. Use the expanded regression suite.

**Step 2: Run test to verify it fails**

Not applicable.

**Step 3: Write minimal implementation**

No code changes.

**Step 4: Run test to verify it passes**

Run: `pytest -v`
Expected: PASS.

Run: `python scheduler/manage_cron.py --print`
Expected: shows a noon cron entry by default.

**Step 5: Commit**

```bash
git add README.md .env.example config.py main.py scheduler/cron.example tests/test_config.py tests/test_main.py tests/test_smoke.py
git commit -m "feat: add simplified daily email backfill"
```
