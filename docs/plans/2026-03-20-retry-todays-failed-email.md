# Retry Today's Failed Email Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically retry today's failed noon or evening email once on every program run before the normal scheduled delivery flow continues.

**Architecture:** Keep `main.py` as the only runtime entrypoint and add a small retry pass near the start of `run()`. Reuse the existing noon and evening delivery functions so retry behavior stays aligned with current message generation, state updates, and duplicate-send guards.

**Tech Stack:** Python 3, datetime stdlib, zoneinfo, pathlib, smtplib, pytest

---

### Task 1: Add a failing test for retrying today's failed noon email

**Files:**
- Modify: `tests/test_main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_retries_todays_failed_noon_email(monkeypatch, tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=False,
            notice_urls=["http://example.com/a"],
            status="failed",
            warning_emitted=True,
        )
    )
    calls = {"send": 0}
    monkeypatch.setattr("main.Settings.from_env", lambda: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 20, 12, 5)
    )
    monkeypatch.setattr("main.collect_notices_for_date", lambda _settings, _date: [])
    monkeypatch.setattr(
        "main.send_email",
        lambda _settings, subject, body, html_body: calls.__setitem__("send", calls["send"] + 1),
    )

    assert run() == 0
    assert calls["send"] == 1
    assert store.get_record("2026-03-20", "noon")["email_sent"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_retries_todays_failed_noon_email -v`
Expected: FAIL because `run()` does not currently retry today's failed noon record outside the exact noon slot.

**Step 3: Write minimal implementation**

Add a helper in `main.py` that checks today's `noon` and `evening` records for `status == "failed"` and `email_sent == False`, then calls the matching delivery function.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_retries_todays_failed_noon_email -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: retry today's failed email on startup"
```

### Task 2: Add a failing test for avoiding duplicate send after successful retry

**Files:**
- Modify: `tests/test_main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_does_not_send_twice_after_retrying_failed_noon(monkeypatch, tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(get_state_path(str(tmp_path)))
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=False,
            notice_urls=["http://example.com/a"],
            status="failed",
            warning_emitted=True,
        )
    )
    calls = {"send": 0}
    monkeypatch.setattr("main.Settings.from_env", lambda: settings)
    monkeypatch.setattr(
        "main.get_current_time", lambda _settings: datetime(2026, 3, 20, 12, 0)
    )
    monkeypatch.setattr("main.collect_notices_for_date", lambda _settings, _date: [])
    monkeypatch.setattr(
        "main.send_email",
        lambda _settings, subject, body, html_body: calls.__setitem__("send", calls["send"] + 1),
    )

    assert run() == 0
    assert calls["send"] == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_does_not_send_twice_after_retrying_failed_noon -v`
Expected: FAIL because a naive retry implementation could send once during retry and once again during the scheduled noon path.

**Step 3: Write minimal implementation**

Ensure the retry path writes a successful state update before the scheduled slot logic runs, so `process_noon_delivery()` exits through the existing duplicate-success guard.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_does_not_send_twice_after_retrying_failed_noon -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "fix: avoid duplicate noon send after startup retry"
```

### Task 3: Implement today's failed email retry helper

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

Reuse the tests from Tasks 1 and 2 as the failing contract for the new helper.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_retries_todays_failed_noon_email tests/test_main.py::test_run_does_not_send_twice_after_retrying_failed_noon -v`
Expected: FAIL before the helper exists.

**Step 3: Write minimal implementation**

Add a helper similar to:

```python
def retry_failed_deliveries_for_today(
    settings: Settings, store: DeliveryStateStore, now: datetime
) -> None:
    today = now.date().isoformat()
    noon = store.get_record(today, "noon")
    if noon and noon.get("status") == "failed" and not bool(noon.get("email_sent")):
        process_noon_delivery(settings, store, now)

    evening = store.get_record(today, "evening")
    if evening and evening.get("status") == "failed" and not bool(evening.get("email_sent")):
        process_evening_delivery(settings, store, now)
```

Call it from `run()` after cleanup and before `send_backfill_if_needed(...)` or slot dispatch.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_retries_todays_failed_noon_email tests/test_main.py::test_run_does_not_send_twice_after_retrying_failed_noon -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: retry today's failed delivery records"
```

### Task 4: Run the targeted regression suite

**Files:**
- Modify: none
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

No new test code. Use the existing targeted regression set.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: Any pre-existing failures must be understood before proceeding.

**Step 3: Write minimal implementation**

No new production changes. Only fix issues directly caused by the retry change.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "test: verify startup retry behavior for failed emails"
```
