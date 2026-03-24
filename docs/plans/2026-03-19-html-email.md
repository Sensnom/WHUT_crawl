# HTML Email Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve outbound HTML emails so they look cleaner and render summary Markdown as readable email content while preserving plain text fallback.

**Architecture:** Keep the existing SMTP path and plain text body generation. Extend `email_sender.py` with a lightweight Markdown-to-HTML renderer plus improved card-style HTML templates for daily, evening, and backfill emails, then keep sending every message as `multipart/alternative`.

**Tech Stack:** Python 3.10+, `email.message.EmailMessage`, SMTP, pytest

---

### Task 1: Add failing tests for Markdown-to-HTML rendering

**Files:**
- Modify: `tests/test_email_sender.py`

**Step 1: Write the failing test for list and paragraph rendering**

```python
def test_render_markdown_as_email_html_formats_lists_and_paragraphs():
    html = render_markdown_as_email_html("- 要点一\n- 要点二\n\n结论段落")
    assert "<ul" in html
    assert "<li>要点一</li>" in html
    assert "<p" in html
    assert "结论段落" in html
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_email_sender.py::test_render_markdown_as_email_html_formats_lists_and_paragraphs -v`
Expected: FAIL because the Markdown renderer does not exist yet.

**Step 3: Extend failing coverage for supported syntax**

Add tests for:
- `#` / `##` headings
- `**bold**` inline emphasis
- `> quote` blockquotes
- `---` divider rendering
- safety escaping for `<script>`-like input

**Step 4: Run focused tests to verify failures are real**

Run: `uv run pytest tests/test_email_sender.py -v`
Expected: FAIL only on the new Markdown rendering expectations.

### Task 2: Implement a lightweight Markdown renderer for email-safe HTML

**Files:**
- Modify: `email_sender.py`
- Test: `tests/test_email_sender.py`

**Step 1: Write minimal implementation for block parsing**

Add a helper that renders only the subset this project needs.

```python
def render_markdown_as_email_html(markdown: str) -> str:
    blocks = []
    ...
    return "".join(blocks)
```

**Step 2: Keep it intentionally small**

Support only:
- headings with `#` and `##`
- unordered lists with `- ` or `* `
- paragraphs
- `**bold**`
- blockquotes with `> `
- `---` dividers

Escape content first and do not support raw HTML passthrough.

**Step 3: Run focused tests**

Run: `uv run pytest tests/test_email_sender.py -v`
Expected: PASS for Markdown rendering tests.

### Task 3: Refresh daily HTML template styling

**Files:**
- Modify: `email_sender.py`
- Test: `tests/test_email_sender.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test for card-style HTML structure**

Add or update tests so daily HTML must include:
- a visible badge marker for `每日摘要`
- a summary card/container hook
- a notice list card/container hook
- rendered list HTML instead of raw Markdown source markers

**Step 2: Run the targeted test to verify it fails**

Run: `uv run pytest tests/test_email_sender.py::test_build_email_html_contains_summary_and_notice_links -v`
Expected: FAIL on the new structure expectations.

**Step 3: Implement minimal template improvements**

Update `build_email_html(...)` to:
- use a cleaner container/card hierarchy
- render summary via `render_markdown_as_email_html(summary)`
- keep notice items as readable blocks with title/date/link
- preserve the noon/evening badge variant behavior

**Step 4: Run focused tests**

Run: `uv run pytest tests/test_email_sender.py tests/test_main.py -v`
Expected: PASS for the daily and evening HTML tests.

### Task 4: Improve backfill HTML rendering

**Files:**
- Modify: `email_sender.py`
- Test: `tests/test_email_sender.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test for backfill section rendering**

Add or update a test so backfill HTML must:
- show the backfill badge
- show the date range
- render each day as a readable section
- render Markdown section content through the renderer instead of wrapping everything in `<pre>`

**Step 2: Run the targeted test to verify it fails**

Run: `uv run pytest tests/test_email_sender.py::test_build_backfill_html_contains_date_range_and_sections -v`
Expected: FAIL because backfill content is still rendered as a raw code-style block.

**Step 3: Implement minimal backfill template improvements**

Update `build_backfill_html(...)` so each date section uses normal block layout and rendered HTML content.

**Step 4: Run targeted tests**

Run: `uv run pytest tests/test_email_sender.py tests/test_main.py -v`
Expected: PASS.

### Task 5: Verify compatibility and regressions

**Files:**
- Verify: `email_sender.py`
- Verify: `main.py`
- Verify: `tests/test_email_sender.py`
- Verify: `tests/test_main.py`
- Verify: `tests/test_backfill.py`

**Step 1: Run focused regression suite**

Run: `uv run pytest tests/test_email_sender.py tests/test_main.py tests/test_backfill.py -v`
Expected: PASS.

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS.

**Step 3: Review delivered message behavior**

Confirm that:
- every outbound email still includes plain text and HTML
- summary Markdown is rendered as readable HTML instead of source text
- noon, evening, and backfill variants remain visually distinguishable
- QQ SMTP and other SMTP transport behavior remain unchanged
