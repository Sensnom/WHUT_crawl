# WHUT Local Summary Reuse Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reuse today's local summary file for email delivery when it already exists, instead of re-crawling and re-summarizing.

**Architecture:** Add a small helper in `main.py` to compute today's summary path and check whether it exists. When present, read the markdown file, send it as the email body, and skip network crawling and DeepSeek summarization; otherwise keep the current full pipeline unchanged.

**Tech Stack:** Python 3, pathlib, existing SMTP/email flow, pytest

---

### Task 1: Detect today's summary file

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_get_summary_file_path_for_today(tmp_path):
    path = get_summary_file_path_for_date(tmp_path, datetime(2026, 3, 18))
    assert path.name == "summary_20260318.md"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_get_summary_file_path_for_date -v`
Expected: FAIL because helper does not exist yet.

**Step 3: Write minimal implementation**

Add helper:

```python
def get_summary_file_path_for_date(output_dir: str, when: datetime | None = None) -> Path:
    ts = when or datetime.now()
    return Path(output_dir) / f"summary_{ts:%Y%m%d}.md"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_get_summary_file_path_for_date -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add today's summary file helper"
```

### Task 2: Reuse local summary file when present

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_reuses_local_summary_file(monkeypatch, tmp_path):
    summary_file = tmp_path / "summary_20260318.md"
    summary_file.write_text("cached summary", encoding="utf-8")
    ...
    assert run() == 0
    assert collect_recent_notices was not called
    assert sent_body contains "cached summary"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_reuses_local_summary_file -v`
Expected: FAIL because `run()` always crawls now.

**Step 3: Write minimal implementation**

In `run()`:
- compute today's summary file path first
- if file exists, read it and send email directly
- print a short message such as `使用本地摘要文件: ...`
- skip `collect_recent_notices`, detail fetch, and summarization

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_reuses_local_summary_file -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: reuse local summary file for email delivery"
```

### Task 3: Fallback to normal pipeline when local file missing or unreadable

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_falls_back_to_live_pipeline_when_cache_missing(monkeypatch, tmp_path):
    ...
    assert run() == 0
    assert collect_recent_notices was called once
```
```

Optionally add a second test for read failure if needed.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_falls_back_to_live_pipeline_when_cache_missing -v`
Expected: FAIL until fallback behavior is explicit.

**Step 3: Write minimal implementation**

Ensure:
- only existing readable file triggers reuse
- missing/unreadable file continues with current crawl/summarize logic

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: fall back to live summary generation when cache unavailable"
```

### Task 4: End-to-end verification and docs touch-up

**Files:**
- Modify: `README.md`

**Step 1: Write the failing test**

Add a docs assertion that `README.md` mentions local summary reuse.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL until docs mention cache reuse.

**Step 3: Write minimal implementation**

Document:
- if today's summary file already exists, the script reuses it for email sending
- delete the file if you want to force a fresh crawl/summarization

**Step 4: Run test to verify it passes**

Run: `pytest -v && python3 main.py`
Expected: tests pass; if today's file exists, output indicates local reuse path.

**Step 5: Commit**

```bash
git add README.md tests/test_smoke.py main.py
git commit -m "docs: explain local summary reuse behavior"
```
