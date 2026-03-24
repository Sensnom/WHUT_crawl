# Course Task Always-Send After Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make course-task emails send on every `main.py` run, even if the same course-task slot already sent successfully earlier that day.

**Architecture:** Keep the current single-entry runtime and service split, but remove the duplicate-send guard from the course-task service path only. Preserve state recording and artifact writing so the system still stores the latest send result for the day and slot without using that state to block future course-task sends.

**Tech Stack:** Python 3, pytest, pathlib, existing service-layer architecture

---

### Task 1: Replace the service-level duplicate-skip rule

**Files:**
- Modify: `services/course_service.py`
- Modify: `tests/test_course_service.py`

**Step 1: Write the failing test**

```python
def test_process_course_task_delivery_sends_again_even_when_today_already_succeeded(tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="course_tasks_noon",
            summary_path=str(tmp_path / "course_tasks_20260320_noon.md"),
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )
    send_calls = {"count": 0}

    process_course_task_delivery(
        settings,
        store,
        datetime(2026, 3, 20, 0, 0),
        "noon",
        get_course_task_slot_fn=lambda slot: f"course_tasks_{slot}",
        get_course_task_artifact_path_fn=lambda output_dir, target_date, slot: Path(output_dir) / f"course_tasks_{target_date:%Y%m%d}_{slot}.md",
        send_course_task_email_fn=lambda *_args: send_calls.__setitem__("count", send_calls["count"] + 1) or ("课程提醒", "正文", "<p>正文</p>"),
        write_course_task_artifact_fn=lambda output_dir, *_args: Path(output_dir) / "course_tasks_20260320_noon.md",
        save_delivery_record_fn=lambda *_args, **_kwargs: None,
    )

    assert send_calls["count"] == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_course_service.py::test_process_course_task_delivery_sends_again_even_when_today_already_succeeded -v`
Expected: FAIL because `process_course_task_delivery()` still returns early when a successful same-day record exists.

**Step 3: Write minimal implementation**

Remove the early-return duplicate-send branch from `services/course_service.py` while preserving the rest of the send, artifact, and record logic.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_course_service.py::test_process_course_task_delivery_sends_again_even_when_today_already_succeeded -v`
Expected: PASS.

### Task 2: Replace old skip-oriented assertions with latest-result assertions

**Files:**
- Modify: `tests/test_course_service.py`

**Step 1: Write the failing test**

```python
def test_process_course_task_delivery_updates_record_after_repeat_same_day_send(tmp_path: Path):
    settings = make_settings(tmp_path)
    store = DeliveryStateStore(tmp_path / "state.json")
    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="course_tasks_noon",
            summary_path=str(tmp_path / "course_tasks_20260320_noon.md"),
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )

    process_course_task_delivery(...)

    record = store.get_record("2026-03-20", "course_tasks_noon")
    assert record is not None
    assert record["email_sent"] is True
    assert record["status"] == "sent"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_course_service.py::test_process_course_task_delivery_updates_record_after_repeat_same_day_send -v`
Expected: FAIL until the service test expectations align with the new always-send behavior.

**Step 3: Write minimal implementation**

Update the existing duplicate-skip test or replace it with a latest-result assertion so the service test suite matches the requested behavior.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_course_service.py::test_process_course_task_delivery_updates_record_after_repeat_same_day_send -v`
Expected: PASS.

### Task 3: Run focused integration regression for `main.py`

**Files:**
- Verify: `tests/test_main.py`
- Verify: `tests/test_course_service.py`

**Step 1: Run the focused service suite**

Run: `uv run pytest tests/test_course_service.py -v`
Expected: PASS.

**Step 2: Run the focused `main.py` course-task regressions**

Run: `uv run pytest tests/test_main.py -k "course_task or run_sends_empty_course_task_email_when_no_tasks or run_records_separate_state_for_course_tasks" -v`
Expected: PASS.

**Step 3: Run manual behavior smoke check if desired**

Run: `uv run python main.py`
Expected: when the course-task branch executes, it sends again even if the same day already recorded a successful course-task delivery.
