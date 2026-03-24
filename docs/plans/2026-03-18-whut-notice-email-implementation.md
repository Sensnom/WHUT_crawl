# WHUT Notice Email Delivery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the WHUT notice crawler so it sends a daily Gmail email containing the AI summary and source notice links after generating the local markdown summary.

**Architecture:** Keep the existing crawl-and-summarize pipeline in `main.py`, add SMTP configuration to `config.py`, and introduce a focused `email_sender.py` module that builds and sends a plain-text Gmail message. The pipeline still writes `output/summary_YYYYMMDD.md`, then sends email as a final delivery step and logs any SMTP failures without losing the saved summary.

**Tech Stack:** Python 3, smtplib/email stdlib, requests, beautifulsoup4, python-dotenv, pytest

---

### Task 1: Add SMTP configuration support

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_settings_reads_smtp_fields(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "y2902341094@gmail.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app-pass")
    monkeypatch.setenv("EMAIL_TO", "y2902341094@gmail.com")
    settings = Settings.from_env()
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 587
    assert settings.smtp_user == "y2902341094@gmail.com"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_reads_smtp_fields -v`
Expected: FAIL because SMTP fields do not exist yet.

**Step 3: Write minimal implementation**

```python
@dataclass
class Settings:
    ...
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_app_password: str = ""
    email_to: str = ""
```

Update `Settings.from_env()` to load all five SMTP/email values and update `.env.example` with matching keys.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_settings_reads_smtp_fields -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add config.py .env.example tests/test_config.py
git commit -m "feat: add smtp configuration support"
```

### Task 2: Build email subject and body formatter

**Files:**
- Create: `email_sender.py`
- Test: `tests/test_email_sender.py`

**Step 1: Write the failing test**

```python
def test_build_email_body_contains_summary_and_links():
    notices = [NoticeItem(...)]
    body = build_email_body("- 要点1", notices, "本科生院")
    assert "要点1" in body
    assert "原始通知链接" in body
    assert "http://example.com/a" in body
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_email_sender.py::test_build_email_body_contains_summary_and_links -v`
Expected: FAIL because module/functions do not exist yet.

**Step 3: Write minimal implementation**

```python
def build_email_subject(target_source: str, now: datetime | None = None) -> str:
    ts = now or datetime.now()
    return f"WHUT {target_source}通知摘要 {ts:%Y-%m-%d}"


def build_email_body(summary: str, notices: list[NoticeItem], target_source: str) -> str:
    lines = [
        f"{target_source}最近三天通知摘要",
        "",
        "AI 总结:",
        summary.strip(),
        "",
        "原始通知链接:",
    ]
    for item in notices:
        lines.append(f"- {item.title}: {item.url}")
    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_email_sender.py::test_build_email_body_contains_summary_and_links -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add email_sender.py tests/test_email_sender.py
git commit -m "feat: format daily summary emails"
```

### Task 3: Implement Gmail SMTP sending

**Files:**
- Modify: `email_sender.py`
- Test: `tests/test_email_sender.py`

**Step 1: Write the failing test**

```python
def test_send_email_uses_tls_and_login(monkeypatch):
    calls = []
    class FakeSMTP:
        ...
    monkeypatch.setattr("email_sender.smtplib.SMTP", FakeSMTP)
    send_email(settings, "subject", "body")
    assert calls == ["starttls", ("login", "user"), "send_message"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_email_sender.py::test_send_email_uses_tls_and_login -v`
Expected: FAIL because SMTP send function does not exist yet.

**Step 3: Write minimal implementation**

```python
def send_email(settings: Settings, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_user
    msg["To"] = settings.email_to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_app_password)
        smtp.send_message(msg)
```

Add a small `validate_email_settings(settings)` helper that raises a clear `ValueError` when required SMTP config is missing.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_email_sender.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add email_sender.py tests/test_email_sender.py
git commit -m "feat: send summary email through gmail smtp"
```

### Task 4: Integrate email sending into pipeline

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_writes_file_even_if_email_send_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(...)
    exit_code = run()
    assert exit_code == 0
    assert list(tmp_path.glob("summary_*.md"))
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_writes_file_even_if_email_send_fails -v`
Expected: FAIL because pipeline does not send email yet and/or cannot exercise fallback.

**Step 3: Write minimal implementation**

Update `main.py` to:
- import `build_email_subject`, `build_email_body`, and `send_email`
- create subject/body after generating the summary markdown
- call `send_email`
- catch SMTP/value errors, print warning, and still return success if summary file was saved

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: email daily notice summary after generation"
```

### Task 5: Update docs and cron template

**Files:**
- Modify: `README.md`
- Modify: `scheduler/cron.example`

**Step 1: Write the failing test**

Add a small docs regression test in `tests/test_smoke.py` that checks key SMTP env names are documented in `README.md`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL until docs mention SMTP settings.

**Step 3: Write minimal implementation**

Update docs with:
- Gmail App Password setup note
- `.env` fields for SMTP
- command usage
- daily 08:00 cron example targeting this project

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS or SKIPPED only for live-network conditions, not for docs coverage.

**Step 5: Commit**

```bash
git add README.md scheduler/cron.example tests/test_smoke.py
git commit -m "docs: add gmail setup and daily cron usage"
```

### Task 6: End-to-end verification

**Files:**
- Modify: `.env` (local only, do not commit secrets)

**Step 1: Write the failing test**

No new automated test. Create a one-off verification checklist instead:
- local summary file created
- email subject correct
- email reaches inbox

**Step 2: Run verification command**

Run: `python3 main.py`
Expected: summary prints, `output/summary_YYYYMMDD.md` exists, Gmail send succeeds.

**Step 3: Write minimal implementation**

If verification fails:
- fix only the proven failure (SMTP auth, timeout, body formatting, etc.)
- re-run `python3 main.py`

**Step 4: Run full verification**

Run: `pytest -v && python3 main.py`
Expected: tests pass and email arrives.

**Step 5: Commit**

```bash
git add config.py email_sender.py main.py README.md tests
git commit -m "feat: deliver daily notice summaries by email"
```
