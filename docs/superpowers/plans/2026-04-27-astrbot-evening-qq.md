# AstrBot Evening QQ Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional AstrBot QQ sender that posts the evening school-news summary once per day without changing the existing noon email, backfill email, or course-task email behavior.

**Architecture:** Keep the current summary-generation and SMTP paths intact. Add a small AstrBot transport module plus a QQ-friendly formatter, then wire both into `services/news_service.py` so evening delivery can attempt email and AstrBot independently while recording channel-specific results.

**Tech Stack:** Python 3.10+, `requests`, `pytest`, existing dataclass-based settings and JSON delivery state store.

---

### Task 1: Add AstrBot configuration and state fields

**Files:**
- Modify: `config.py`
- Modify: `delivery_state.py`
- Modify: `main.py`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_config.py`
- Test: `tests/test_delivery_state.py`

- [ ] **Step 1: Write the failing config tests**

```python
def test_settings_reads_astrbot_fields(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_ASTRBOT_SERVICE", "true")
    monkeypatch.setenv("ASTRBOT_BASE_URL", "http://localhost:6185")
    monkeypatch.setenv("ASTRBOT_API_KEY", "abk_test")
    monkeypatch.setenv("ASTRBOT_UMO", "onebot:group:123456")

    settings = Settings.from_env()

    assert settings.enable_astrbot_service is True
    assert settings.astrbot_base_url == "http://localhost:6185"
    assert settings.astrbot_api_key == "abk_test"
    assert settings.astrbot_umo == "onebot:group:123456"


def test_settings_require_astrbot_fields_when_enabled(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_ASTRBOT_SERVICE", "true")
    monkeypatch.delenv("ASTRBOT_API_KEY", raising=False)
    monkeypatch.delenv("ASTRBOT_UMO", raising=False)

    with pytest.raises(ValueError, match="ASTRBOT"):
        Settings.from_env()
```

- [ ] **Step 2: Run the config tests to confirm they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL because `Settings` does not yet expose AstrBot fields or validation.

- [ ] **Step 3: Extend `Settings` and validation in `config.py`**

```python
@dataclass
class Settings:
    api_key: str
    base_url: str
    model: str
    request_timeout: int
    list_url: str = "http://i.whut.edu.cn/xxtg/"
    output_dir: str = str(PROJECT_ROOT / "output")
    target_source: str = "本科生院"
    max_pages: int = 3
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_app_password: str = ""
    email_to: str = ""
    enable_astrbot_service: bool = False
    astrbot_base_url: str = "http://localhost:6185"
    astrbot_api_key: str = ""
    astrbot_umo: str = ""
```

```python
def _validate_astrbot_settings(settings: "Settings") -> None:
    if not settings.enable_astrbot_service:
        return

    errors: list[str] = []
    if not settings.astrbot_base_url:
        errors.append("ASTRBOT_BASE_URL 不能为空")
    if not settings.astrbot_api_key:
        errors.append("ASTRBOT_API_KEY 不能为空")
    if not settings.astrbot_umo:
        errors.append("ASTRBOT_UMO 不能为空")
    if errors:
        raise ValueError("配置错误: " + "; ".join(errors))
```

```python
settings = cls(
    # existing fields omitted for brevity
    enable_astrbot_service=parse_bool_env(
        "ENABLE_ASTRBOT_SERVICE",
        os.getenv("ENABLE_ASTRBOT_SERVICE", "false"),
    ),
    astrbot_base_url=os.getenv("ASTRBOT_BASE_URL", "http://localhost:6185").strip(),
    astrbot_api_key=os.getenv("ASTRBOT_API_KEY", "").strip(),
    astrbot_umo=os.getenv("ASTRBOT_UMO", "").strip(),
)

if validate:
    validate_settings(settings)
```

```python
def validate_settings(settings: "Settings") -> None:
    _validate_common_settings(settings)
    _validate_astrbot_settings(settings)
```

- [ ] **Step 4: Add AstrBot fields to delivery records and `save_delivery_record`**

```python
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
    astrbot_sent: bool = False
    astrbot_error: str = ""
```

```python
def save_delivery_record(
    store: DeliveryStateStore,
    target_date: datetime,
    slot: str,
    summary_path: Path,
    notice_urls: list[str],
    email_sent: bool,
    status: str,
    warning_emitted: bool = False,
    backfilled: bool = False,
    now: datetime | None = None,
    astrbot_sent: bool = False,
    astrbot_error: str = "",
) -> None:
    timestamp = (now or datetime.now()).isoformat()
    sent_at = timestamp if email_sent else ""
    store.record(
        DeliveryRecord(
            date=target_date.date().isoformat(),
            slot=slot,
            summary_path=str(summary_path),
            email_sent=email_sent,
            notice_urls=notice_urls,
            status=status,
            warning_emitted=warning_emitted,
            sent_at=sent_at,
            updated_at=timestamp,
            backfilled=backfilled,
            astrbot_sent=astrbot_sent,
            astrbot_error=astrbot_error,
        )
    )
```

- [ ] **Step 5: Document the new env vars**

```env
ENABLE_ASTRBOT_SERVICE=false
ASTRBOT_BASE_URL=http://localhost:6185
ASTRBOT_API_KEY=abk_your_api_key
ASTRBOT_UMO=onebot:group:123456789
```

Add the same four variables to `.env.example`, and add a short README section stating that QQ evening push uses AstrBot `POST /api/v1/im/message` and only sends school-news summaries during the evening run.

- [ ] **Step 6: Run the targeted tests again**

Run: `uv run pytest tests/test_config.py tests/test_delivery_state.py -v`
Expected: PASS with AstrBot settings parsing and record serialization covered.

### Task 2: Add the AstrBot sender and QQ message formatter

**Files:**
- Create: `astrbot_sender.py`
- Modify: `main.py`
- Test: `tests/test_astrbot_sender.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing sender and formatter tests**

```python
from datetime import datetime

from main import build_astrbot_news_message
from models import NoticeItem


def test_build_astrbot_news_message_uses_lightweight_layout():
    notices = [
        NoticeItem(
            title="关于组织测试活动的通知",
            url="http://i.whut.edu.cn/test",
            publish_time=datetime(2026, 4, 27, 18, 0),
        )
    ]

    markdown = "# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **测试事项**：今晚提交。\n"

    message = build_astrbot_news_message(markdown, notices)

    assert message.startswith("本科生院最近三天通知总结")
    assert "\n\n摘要\n" in message
    assert "涉及通知" in message
    assert "[" not in message
    assert "http://i.whut.edu.cn/test" in message
```

```python
def test_send_astrbot_message_posts_expected_payload(monkeypatch, tmp_path):
    settings = make_settings(tmp_path)
    settings.enable_astrbot_service = True
    settings.astrbot_base_url = "http://localhost:6185"
    settings.astrbot_api_key = "abk_test"
    settings.astrbot_umo = "onebot:group:123456"
    captured = {}

    class FakeResponse:
        status_code = 200
        text = '{"status":"ok"}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "ok"}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("astrbot_sender.requests.post", fake_post)

    send_astrbot_message(settings, "hello")

    assert captured == {
        "url": "http://localhost:6185/api/v1/im/message",
        "headers": {
            "Authorization": "Bearer abk_test",
            "Content-Type": "application/json",
        },
        "json": {
            "umo": "onebot:group:123456",
            "message": "hello",
        },
        "timeout": 20,
    }
```

- [ ] **Step 2: Run the new targeted tests to confirm they fail**

Run: `uv run pytest tests/test_astrbot_sender.py tests/test_main.py -v`
Expected: FAIL because the AstrBot sender module and message builder do not exist yet.

- [ ] **Step 3: Create `astrbot_sender.py` with a minimal transport-only API**

```python
import requests

from config import Settings


def send_astrbot_message(settings: Settings, message: str, timeout: int = 20) -> None:
    response = requests.post(
        f"{settings.astrbot_base_url.rstrip('/')}/api/v1/im/message",
        headers={
            "Authorization": f"Bearer {settings.astrbot_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "umo": settings.astrbot_umo,
            "message": message,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        raise RuntimeError(f"AstrBot send failed: {payload}")
```

- [ ] **Step 4: Add a QQ-friendly formatter in `main.py`**

```python
def build_astrbot_news_message(markdown: str, notices: list[NoticeItem]) -> str:
    lines = markdown.strip().splitlines()
    title = lines[0].lstrip("# ").strip() if lines else "通知总结"
    summary_lines: list[str] = []
    in_summary = False

    for raw_line in lines[1:]:
        line = raw_line.strip()
        if line == "## 摘要":
            in_summary = True
            continue
        if line.startswith("## ") and in_summary:
            break
        if in_summary and line:
            summary_lines.append(line)

    lines = [
        title,
        "",
        "摘要",
        "\n".join(summary_lines) if summary_lines else "最近三天没有通知。",
    ]

    if notices:
        lines.extend(["", "涉及通知"])
        for index, item in enumerate(notices, start=1):
            lines.extend([
                f"{index}. {item.title}",
                item.url,
                "",
            ])

    return "\n".join(lines).strip() + "\n"
```

Keep this formatter lightweight. It may read the already-generated summary Markdown, but it should not reuse the email HTML renderer or send inline Markdown links.

- [ ] **Step 5: Run the sender and formatter tests again**

Run: `uv run pytest tests/test_astrbot_sender.py tests/test_main.py -v`
Expected: PASS with the new module importable and the message format locked down.

### Task 3: Wire AstrBot into the evening news workflow only

**Files:**
- Modify: `services/news_service.py`
- Modify: `main.py`
- Test: `tests/test_news_service.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing evening-flow tests**

```python
def test_process_evening_delivery_sends_astrbot_when_enabled(tmp_path: Path):
    settings = make_settings(tmp_path)
    settings.enable_astrbot_service = True
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 17, 30),
        )
    ]
    astrbot_calls = []

    store.record(
        DeliveryRecord(
            date="2026-03-20",
            slot="noon",
            summary_path=str(tmp_path / "summary_20260320.md"),
            email_sent=True,
            notice_urls=[],
            status="sent",
        )
    )

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "unused.md",
        collect_notices_for_date_fn=lambda *_args: notices,
        build_notice_outputs_fn=lambda *_args: ("# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **new notice**\n", "body", "<p>body</p>", notices, [notices[0].url]),
        write_summary_file_fn=lambda *_args, **_kwargs: tmp_path / "summary_20260320_evening.md",
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: None,
        send_astrbot_message_fn=lambda _settings, message: astrbot_calls.append(message),
        build_astrbot_news_message_fn=lambda markdown, items: f"qq::{len(items)}::{markdown.splitlines()[-1]}",
        save_delivery_record_fn=lambda *args, **kwargs: None,
    )

    assert astrbot_calls == ["qq::1::1. **new notice**"]
```

```python
def test_process_noon_delivery_never_sends_astrbot(tmp_path: Path):
    settings = make_settings(tmp_path)
    now = datetime(2026, 3, 20, 12, 0)

    process_noon_delivery(
        settings,
        DeliveryStateStore(tmp_path / "state.json"),
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "summary.md",
        collect_notices_for_date_fn=lambda *_args: [],
        trim_notices_to_cutoff_fn=lambda items, *_args: items,
        build_notice_outputs_fn=lambda *_args: ("# summary\n", "body", "<p>body</p>", [], []),
        write_summary_file_fn=lambda *_args, **_kwargs: tmp_path / "summary.md",
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: None,
        save_delivery_record_fn=lambda *args, **kwargs: None,
    )
```

- [ ] **Step 2: Run the evening-flow tests to confirm they fail**

Run: `uv run pytest tests/test_news_service.py tests/test_main.py -v`
Expected: FAIL because `process_evening_delivery` does not yet accept AstrBot hooks or persist AstrBot status.

- [ ] **Step 3: Inject AstrBot into `main.py` and `services/news_service.py`**

```python
from astrbot_sender import send_astrbot_message
```

```python
def process_evening_delivery(
    settings: Settings, store: DeliveryStateStore, now: datetime
) -> int:
    return process_evening_delivery_service(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=get_summary_file_path_for_date,
        collect_notices_for_date_fn=collect_notices_for_date,
        build_notice_outputs_fn=build_notice_outputs,
        write_summary_file_fn=write_summary_file,
        build_email_subject_fn=build_email_subject,
        send_email_fn=send_email,
        send_astrbot_message_fn=send_astrbot_message,
        build_astrbot_news_message_fn=build_astrbot_news_message,
        save_delivery_record_fn=save_delivery_record,
    )
```

```python
email_sent = False
astrbot_sent = False
astrbot_error = ""

try:
    send_email_fn(settings, subject, body, html)
    email_sent = True
except (ValueError, RuntimeError, smtplib.SMTPException, OSError) as exc:
    print_fn(f"[WARN] 邮件发送失败: {exc}")

if settings.enable_astrbot_service:
    try:
        qq_message = build_astrbot_news_message_fn(markdown, _items)
        send_astrbot_message_fn(settings, qq_message)
        astrbot_sent = True
    except (RuntimeError, OSError, ValueError) as exc:
        astrbot_error = str(exc)
        print_fn(f"[WARN] AstrBot 发送失败: {exc}")

status = "sent" if email_sent or astrbot_sent else "failed"
save_delivery_record_fn(
    store,
    target_date,
    "evening",
    evening_output,
    notice_urls,
    email_sent,
    status,
    warning_emitted=not (email_sent or astrbot_sent),
    now=now,
    astrbot_sent=astrbot_sent,
    astrbot_error=astrbot_error,
)
```

Use the real `markdown` content already returned from `build_notice_outputs_fn` rather than rereading the summary artifact from disk.

- [ ] **Step 4: Add a regression test for email failure plus AstrBot success**

```python
def test_process_evening_delivery_still_attempts_astrbot_after_email_failure(tmp_path: Path):
    settings = make_settings(tmp_path)
    settings.enable_astrbot_service = True
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    astrbot_calls = []
    saved = {}
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 17, 30),
        )
    ]

    process_evening_delivery(
        settings,
        store,
        now,
        get_summary_file_path_for_date_fn=lambda *_args, **_kwargs: tmp_path / "unused.md",
        collect_notices_for_date_fn=lambda *_args: notices,
        build_notice_outputs_fn=lambda *_args: ("# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **new notice**\n", "1. **new notice**", "<p>body</p>", notices, [notices[0].url]),
        write_summary_file_fn=lambda *_args, **_kwargs: tmp_path / "summary_20260320_evening.md",
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: (_ for _ in ()).throw(RuntimeError("smtp down")),
        send_astrbot_message_fn=lambda _settings, message: astrbot_calls.append(message),
        build_astrbot_news_message_fn=lambda markdown, items: f"qq::{len(items)}::{markdown.splitlines()[-1]}",
        save_delivery_record_fn=lambda *args, **kwargs: saved.update({"args": args, "kwargs": kwargs}),
    )

    assert astrbot_calls == ["qq::1::1. **new notice**"]
    assert saved["kwargs"]["astrbot_sent"] is True
    assert saved["args"][5] is False
    assert saved["args"][6] == "sent"
```

- [ ] **Step 5: Run the targeted workflow tests**

Run: `uv run pytest tests/test_news_service.py tests/test_main.py -v`
Expected: PASS with evening-only AstrBot delivery and channel-independent error handling verified.

- [ ] **Step 6: Run the focused full regression set**

Run: `uv run pytest tests/test_config.py tests/test_delivery_state.py tests/test_astrbot_sender.py tests/test_news_service.py tests/test_main.py -v`
Expected: PASS.

### Notes

- Do not add direct NapCat support in this implementation.
- Do not send course-task or backfill messages to AstrBot.
- Do not add git commit steps; the user explicitly asked not to use git for this work.
