# WHUT Notice Crawler Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python project that crawls `http://i.whut.edu.cn/xxtg/`, filters notices from the last 72 hours, summarizes content with DeepSeek, and outputs results to both terminal and Markdown files with optional cron scheduling.

**Architecture:** The app is a small pipeline: fetch list page, parse notice metadata, filter by publish time, fetch detail pages, then call DeepSeek for concise Chinese bullet summaries. The code is split into focused modules (`config`, `crawler`, `parser`, `summarizer`, `main`) with data models in one place and tests per module. Errors degrade gracefully so scheduled jobs still produce usable output.

**Tech Stack:** Python 3, requests, beautifulsoup4, python-dotenv, pytest

---

### Task 1: Project scaffold and configuration loading

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `config.py`
- Create: `models.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
from config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    s = Settings.from_env()
    assert s.api_key == "test-key"
    assert s.base_url == "https://api.deepseek.com"
    assert s.model == "deepseek-chat"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_from_env -v`
Expected: FAIL with import/class missing errors.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass
class Settings:
    api_key: str
    base_url: str
    model: str
    request_timeout: int = 20

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "20")),
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_settings_from_env -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add requirements.txt .env.example .gitignore config.py models.py tests/test_config.py
git commit -m "feat: add project scaffold and env configuration"
```

### Task 2: List-page parser and 72-hour filter

**Files:**
- Create: `parser.py`
- Create: `tests/test_parser.py`

**Step 1: Write the failing test**

```python
from datetime import datetime
from parser import filter_recent_notices


def test_filter_recent_notices_keeps_only_last_72_hours():
    now = datetime(2026, 3, 18, 12, 0, 0)
    notices = [
        {"title": "new", "publish_time": datetime(2026, 3, 17, 12, 0, 0)},
        {"title": "old", "publish_time": datetime(2026, 3, 14, 11, 59, 59)},
    ]
    result = filter_recent_notices(notices, now)
    assert [n["title"] for n in result] == ["new"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_parser.py::test_filter_recent_notices_keeps_only_last_72_hours -v`
Expected: FAIL because function/module does not exist yet.

**Step 3: Write minimal implementation**

```python
from datetime import timedelta


def filter_recent_notices(notices, now):
    threshold = now - timedelta(hours=72)
    return [n for n in notices if n["publish_time"] >= threshold]
```

Then add list-page parsing helper:
- `parse_list_page(html: str, base_url: str) -> list[NoticeItem]`
- Extract title/link/publish time from HTML structure.
- Parse publish time with a strict formatter and skip invalid rows with warning.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_parser.py -v`
Expected: PASS for filter test and parser tests.

**Step 5: Commit**

```bash
git add parser.py tests/test_parser.py
git commit -m "feat: parse notice list and apply 72-hour filter"
```

### Task 3: HTTP crawler for list/detail pages with retries

**Files:**
- Create: `crawler.py`
- Create: `tests/test_crawler.py`

**Step 1: Write the failing test**

```python
import requests
from crawler import fetch_html


def test_fetch_html_returns_text(requests_mock):
    requests_mock.get("http://example.com", text="ok")
    assert fetch_html("http://example.com", timeout=10) == "ok"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_crawler.py::test_fetch_html_returns_text -v`
Expected: FAIL due to missing crawler implementation.

**Step 3: Write minimal implementation**

```python
import time
import requests


def fetch_html(url, timeout=20, retries=2):
    last_err = None
    for i in range(retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            last_err = exc
            if i < retries:
                time.sleep(2 ** i)
    raise last_err
```

Then add detail helper:
- `fetch_notice_detail(url, timeout, retries)` returns cleaned text content.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_crawler.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add crawler.py tests/test_crawler.py
git commit -m "feat: add robust html fetching with retry"
```

### Task 4: DeepSeek summarizer and output formatting

**Files:**
- Create: `summarizer.py`
- Create: `tests/test_summarizer.py`

**Step 1: Write the failing test**

```python
from summarizer import build_prompt


def test_build_prompt_contains_notice_fields():
    notices = [{"title": "t1", "publish_time": "2026-03-18 09:00", "url": "u", "content": "c"}]
    prompt = build_prompt(notices)
    assert "t1" in prompt
    assert "2026-03-18 09:00" in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_summarizer.py::test_build_prompt_contains_notice_fields -v`
Expected: FAIL due to missing module/functions.

**Step 3: Write minimal implementation**

```python
import requests


def build_prompt(notices):
    lines = ["请将以下通知总结为中文简明要点（3-8条）："]
    for i, n in enumerate(notices, 1):
        lines.append(f"{i}. 标题: {n['title']}")
        lines.append(f"发布时间: {n['publish_time']}")
        lines.append(f"链接: {n['url']}")
        lines.append(f"正文: {n['content']}")
    return "\n".join(lines)
```

Then add:
- `summarize_with_deepseek(notices, settings)` using chat-completions API.
- fallback text when API fails after retry.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_summarizer.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add summarizer.py tests/test_summarizer.py
git commit -m "feat: add deepseek prompt builder and summarization client"
```

### Task 5: Pipeline orchestration, CLI run, and file output

**Files:**
- Create: `main.py`
- Create: `output/.gitkeep`
- Create: `scheduler/cron.example`
- Create: `README.md`
- Create: `tests/test_main.py`

**Step 1: Write the failing test**

```python
from pathlib import Path
from main import write_summary_file


def test_write_summary_file_creates_markdown(tmp_path: Path):
    out = write_summary_file("hello", output_dir=tmp_path)
    assert out.exists()
    assert out.suffix == ".md"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_write_summary_file_creates_markdown -v`
Expected: FAIL with missing function.

**Step 3: Write minimal implementation**

```python
from datetime import datetime
from pathlib import Path


def write_summary_file(text, output_dir="output"):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"summary_{datetime.now():%Y%m%d}.md"
    path.write_text(text, encoding="utf-8")
    return path
```

Then assemble `main()` pipeline:
- load settings
- fetch and parse list page
- filter 72 hours
- fetch details and truncate content
- call summarizer
- print summary
- write markdown file path to console

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS.

Then run full suite:
- `pytest -v`
Expected: all PASS.

**Step 5: Commit**

```bash
git add main.py output/.gitkeep scheduler/cron.example README.md tests/test_main.py
git commit -m "feat: orchestrate crawl-to-summary pipeline with cli and cron"
```

### Task 6: End-to-end smoke check and docs polish

**Files:**
- Modify: `README.md`
- Modify: `scheduler/cron.example`

**Step 1: Write the failing test**

Add an integration-style smoke test skeleton in `tests/test_smoke.py` that currently fails when expected env var is missing.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL with clear setup message.

**Step 3: Write minimal implementation**

Implement guarded smoke runner:
- if `DEEPSEEK_API_KEY` missing, skip with explicit reason.
- if present, execute one dry run over parsed fixtures (not live network by default).

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS or SKIPPED with reason.

**Step 5: Commit**

```bash
git add README.md scheduler/cron.example tests/test_smoke.py
git commit -m "test: add smoke validation and usage documentation"
```
