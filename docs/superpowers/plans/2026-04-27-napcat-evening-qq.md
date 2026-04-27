# NapCat Evening QQ Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional NapCat QQ sender that posts the evening school-news summary to one or more configured QQ targets without changing the existing noon email, backfill email, or course-task email behavior.

**Architecture:** Reuse the existing summary-generation and SMTP paths. Replace the temporary AstrBot-specific config/state plumbing with NapCat-specific fields, add a transport-only `napcat_sender.py`, then wire evening delivery so email and NapCat targets are attempted independently and recorded separately.

**Tech Stack:** Python 3.10+, `requests`, `pytest`, existing dataclass-based settings and JSON delivery state store.

---

### Task 1: Replace AstrBot config/state scaffolding with NapCat config and result fields

**Files:**
- Modify: `config.py`
- Modify: `delivery_state.py`
- Modify: `main.py`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_config.py`
- Test: `tests/test_delivery_state.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing config and state tests**

```python
def test_settings_reads_napcat_fields(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_NAPCAT_SERVICE", "true")
    monkeypatch.setenv("NAPCAT_BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("NAPCAT_ACCESS_TOKEN", "token")
    monkeypatch.setenv("NAPCAT_TARGETS", "group:123456,private:987654")

    settings = Settings.from_env()

    assert settings.enable_napcat_service is True
    assert settings.napcat_base_url == "http://localhost:3000"
    assert settings.napcat_access_token == "token"
    assert settings.napcat_targets == ["group:123456", "private:987654"]


def test_settings_rejects_invalid_napcat_target(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_NAPCAT_SERVICE", "true")
    monkeypatch.setenv("NAPCAT_BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("NAPCAT_ACCESS_TOKEN", "token")
    monkeypatch.setenv("NAPCAT_TARGETS", "channel:123456")

    with pytest.raises(ValueError, match="NAPCAT_TARGETS"):
        Settings.from_env()
```

```python
def test_delivery_record_persists_napcat_fields(tmp_path):
    state = DeliveryStateStore(tmp_path / "state.json")
    state.record(
        DeliveryRecord(
            date="2026-03-19",
            slot="evening",
            summary_path="output/summary_20260319_evening.md",
            email_sent=True,
            notice_urls=["http://example.com/a"],
            status="sent",
            napcat_sent=False,
            napcat_error="group:123 timeout",
            napcat_target_results=[
                {"target": "group:123", "sent": False, "error": "timeout"}
            ],
        )
    )

    loaded = state.list_records()[0]

    assert loaded["napcat_sent"] is False
    assert loaded["napcat_error"] == "group:123 timeout"
    assert loaded["napcat_target_results"] == [
        {"target": "group:123", "sent": False, "error": "timeout"}
    ]
```

- [ ] **Step 2: Run the targeted tests to confirm they fail**

Run: `uv run pytest tests/test_config.py tests/test_delivery_state.py tests/test_main.py -v`
Expected: FAIL because current code still exposes AstrBot fields and no NapCat result fields.

- [ ] **Step 3: Replace AstrBot settings and validation in `config.py`**

```python
def parse_csv_env(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _validate_napcat_targets(targets: list[str]) -> None:
    for target in targets:
        target_type, _, target_id = target.partition(":")
        if target_type not in {"group", "private"} or not target_id:
            raise ValueError("配置错误: NAPCAT_TARGETS 必须使用 group:<id> 或 private:<id>")
```

```python
def _validate_napcat_settings(settings: "Settings") -> None:
    if not settings.enable_napcat_service:
        return

    errors: list[str] = []
    if not settings.napcat_base_url:
        errors.append("NAPCAT_BASE_URL 不能为空")
    if not settings.napcat_access_token:
        errors.append("NAPCAT_ACCESS_TOKEN 不能为空")
    if not settings.napcat_targets:
        errors.append("NAPCAT_TARGETS 不能为空")
    if errors:
        raise ValueError("配置错误: " + "; ".join(errors))
    _validate_napcat_targets(settings.napcat_targets)
```

```python
@dataclass
class Settings:
    # existing fields omitted
    enable_napcat_service: bool = False
    napcat_base_url: str = ""
    napcat_access_token: str = ""
    napcat_targets: list[str] = field(default_factory=list)
```

```python
settings = cls(
    # existing fields omitted
    enable_napcat_service=parse_bool_env(
        "ENABLE_NAPCAT_SERVICE",
        os.getenv("ENABLE_NAPCAT_SERVICE", "false"),
    ),
    napcat_base_url=os.getenv("NAPCAT_BASE_URL", "").strip(),
    napcat_access_token=os.getenv("NAPCAT_ACCESS_TOKEN", "").strip(),
    napcat_targets=parse_csv_env(os.getenv("NAPCAT_TARGETS", "")),
)
```

```python
def validate_settings(settings: "Settings") -> None:
    _validate_common_settings(settings)
    _validate_napcat_settings(settings)


@staticmethod
def validate_for_mode(settings: "Settings", mode: str) -> None:
    _validate_common_settings(settings, require_api_key=mode != "healthcheck")
    _validate_napcat_settings(settings)
    # existing email-mode logic stays the same
```

- [ ] **Step 4: Replace AstrBot record fields with NapCat result fields**

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
    napcat_sent: bool = False
    napcat_error: str = ""
    napcat_target_results: list[dict[str, object]] = field(default_factory=list)
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
    napcat_sent: bool = False,
    napcat_error: str = "",
    napcat_target_results: list[dict[str, object]] | None = None,
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
            napcat_sent=napcat_sent,
            napcat_error=napcat_error,
            napcat_target_results=napcat_target_results or [],
        )
    )
```

- [ ] **Step 5: Update docs and examples to NapCat names only**

```env
ENABLE_NAPCAT_SERVICE=false
NAPCAT_BASE_URL=http://localhost:3000
NAPCAT_ACCESS_TOKEN=your_token
NAPCAT_TARGETS=group:123456789,private:987654321
```

Update `.env.example` and `README.md` so all user-facing references point to NapCat evening QQ delivery instead of AstrBot.

- [ ] **Step 6: Run the targeted tests again**

Run: `uv run pytest tests/test_config.py tests/test_delivery_state.py tests/test_main.py -v`
Expected: PASS with NapCat settings parsing, validation, and record serialization covered.

### Task 2: Add the NapCat sender and QQ message formatter

**Files:**
- Create: `napcat_sender.py`
- Modify: `main.py`
- Test: `tests/test_napcat_sender.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing sender and formatter tests**

```python
from datetime import datetime

from main import build_napcat_news_message
from models import NoticeItem


def test_build_napcat_news_message_uses_lightweight_layout():
    notices = [
        NoticeItem(
            title="关于组织测试活动的通知",
            url="http://i.whut.edu.cn/test",
            publish_time=datetime(2026, 4, 27, 18, 0),
        )
    ]
    markdown = "# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **测试事项**：今晚提交。\n"

    message = build_napcat_news_message(markdown, notices)

    assert message.startswith("本科生院最近三天通知总结")
    assert "\n\n摘要\n" in message
    assert "涉及通知" in message
    assert "[" not in message
    assert "http://i.whut.edu.cn/test" in message
```

```python
def test_send_napcat_message_posts_group_payload(monkeypatch, tmp_path):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_base_url = "http://localhost:3000"
    settings.napcat_access_token = "token"
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "ok", "retcode": 0}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("napcat_sender.requests.post", fake_post)

    send_napcat_message(settings, "group:123456", "hello")

    assert captured == {
        "url": "http://localhost:3000/send_group_msg",
        "headers": {"Authorization": "Bearer token"},
        "json": {"group_id": 123456, "message": "hello"},
        "timeout": 20,
    }
```

```python
def test_send_napcat_message_posts_private_payload(monkeypatch, tmp_path):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_base_url = "http://localhost:3000"
    settings.napcat_access_token = "token"
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "ok", "retcode": 0}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("napcat_sender.requests.post", fake_post)

    send_napcat_message(settings, "private:987654", "hello")

    assert captured == {
        "url": "http://localhost:3000/send_private_msg",
        "headers": {"Authorization": "Bearer token"},
        "json": {"user_id": 987654, "message": "hello"},
        "timeout": 20,
    }
```

- [ ] **Step 2: Run the targeted tests to confirm they fail**

Run: `uv run pytest tests/test_napcat_sender.py tests/test_main.py -v`
Expected: FAIL because the NapCat sender module and message builder do not exist yet.

- [ ] **Step 3: Create `napcat_sender.py` with target-aware HTTP sending**

```python
import requests

from config import Settings


def send_napcat_message(settings: Settings, target: str, message: str, timeout: int = 20) -> None:
    target_type, target_id = target.split(":", 1)
    if target_type == "group":
        path = "/send_group_msg"
        payload = {"group_id": int(target_id), "message": message}
    elif target_type == "private":
        path = "/send_private_msg"
        payload = {"user_id": int(target_id), "message": message}
    else:
        raise ValueError(f"unsupported NapCat target: {target}")

    response = requests.post(
        f"{settings.napcat_base_url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {settings.napcat_access_token}"},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok" or payload.get("retcode") not in {0, None}:
        raise RuntimeError(f"NapCat send failed: {payload}")
```

- [ ] **Step 4: Add a QQ-friendly formatter in `main.py`**

```python
def build_napcat_news_message(markdown: str, notices: list[NoticeItem]) -> str:
    raw_lines = markdown.strip().splitlines()
    title = raw_lines[0].lstrip("# ").strip() if raw_lines else "通知总结"
    summary_lines: list[str] = []
    in_summary = False

    for raw_line in raw_lines[1:]:
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
            lines.extend([f"{index}. {item.title}", item.url, ""])

    return "\n".join(lines).strip() + "\n"
```

- [ ] **Step 5: Run the sender and formatter tests again**

Run: `uv run pytest tests/test_napcat_sender.py tests/test_main.py -v`
Expected: PASS with the new module importable and message format locked down.

### Task 3: Wire NapCat into the evening news workflow only

**Files:**
- Modify: `services/news_service.py`
- Modify: `main.py`
- Test: `tests/test_news_service.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing evening-flow tests**

```python
def test_process_evening_delivery_sends_napcat_to_all_targets_when_enabled(tmp_path: Path):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456", "private:987654"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 17, 30),
        )
    ]
    napcat_calls = []

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
        send_napcat_message_fn=lambda _settings, target, message: napcat_calls.append((target, message)),
        build_napcat_news_message_fn=lambda markdown, items: f"qq::{len(items)}::{markdown.splitlines()[-1]}",
        save_delivery_record_fn=lambda *args, **kwargs: None,
    )

    assert napcat_calls == [
        ("group:123456", "qq::1::1. **new notice**"),
        ("private:987654", "qq::1::1. **new notice**"),
    ]
```

```python
def test_process_evening_delivery_records_partial_napcat_failures(tmp_path: Path):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456", "private:987654"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    saved = {}
    notices = [
        NoticeItem(
            title="new notice",
            url="https://example.com/new",
            publish_time=datetime(2026, 3, 20, 17, 30),
        )
    ]

    def fake_send_napcat(_settings, target, _message):
        if target == "group:123456":
            raise RuntimeError("timeout")

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
        send_napcat_message_fn=fake_send_napcat,
        build_napcat_news_message_fn=lambda markdown, items: f"qq::{len(items)}::{markdown.splitlines()[-1]}",
        save_delivery_record_fn=lambda *args, **kwargs: saved.update({"args": args, "kwargs": kwargs}),
    )

    assert saved["kwargs"]["napcat_sent"] is False
    assert saved["kwargs"]["napcat_target_results"] == [
        {"target": "group:123456", "sent": False, "error": "timeout"},
        {"target": "private:987654", "sent": True, "error": ""},
    ]
```

- [ ] **Step 2: Run the targeted tests to confirm they fail**

Run: `uv run pytest tests/test_news_service.py tests/test_main.py -v`
Expected: FAIL because `process_evening_delivery` does not yet accept NapCat hooks or persist NapCat results.

- [ ] **Step 3: Inject NapCat into `main.py` and `services/news_service.py`**

```python
from napcat_sender import send_napcat_message
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
        send_napcat_message_fn=send_napcat_message,
        build_napcat_news_message_fn=build_napcat_news_message,
        save_delivery_record_fn=save_delivery_record,
    )
```

```python
email_sent = False
napcat_sent = False
napcat_error = ""
napcat_target_results: list[dict[str, object]] = []

try:
    send_email_fn(settings, subject, body, html)
    email_sent = True
except (ValueError, RuntimeError, smtplib.SMTPException, OSError) as exc:
    print_fn(f"[WARN] 邮件发送失败: {exc}")

if settings.enable_napcat_service:
    qq_message = build_napcat_news_message_fn(markdown, _items)
    for target in settings.napcat_targets:
        try:
            send_napcat_message_fn(settings, target, qq_message)
            napcat_target_results.append({"target": target, "sent": True, "error": ""})
        except (RuntimeError, OSError, ValueError) as exc:
            napcat_target_results.append(
                {"target": target, "sent": False, "error": str(exc)}
            )
            print_fn(f"[WARN] NapCat 发送失败 target={target}: {exc}")

    napcat_sent = bool(napcat_target_results) and all(
        bool(item["sent"]) for item in napcat_target_results
    )
    failed_targets = [item for item in napcat_target_results if not bool(item["sent"])]
    napcat_error = "; ".join(
        f"{item['target']}: {item['error']}" for item in failed_targets
    )

status = "sent" if email_sent or napcat_sent else "failed"
save_delivery_record_fn(
    store,
    target_date,
    "evening",
    evening_output,
    notice_urls,
    email_sent,
    status,
    warning_emitted=not (email_sent or napcat_sent),
    now=now,
    napcat_sent=napcat_sent,
    napcat_error=napcat_error,
    napcat_target_results=napcat_target_results,
)
```

- [ ] **Step 4: Add a regression test for email failure plus successful NapCat delivery**

```python
def test_process_evening_delivery_still_attempts_napcat_after_email_failure(tmp_path: Path):
    settings = make_settings(tmp_path)
    settings.enable_napcat_service = True
    settings.napcat_targets = ["group:123456"]
    store = DeliveryStateStore(tmp_path / "state.json")
    now = datetime(2026, 3, 20, 18, 0)
    napcat_calls = []
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
        build_notice_outputs_fn=lambda *_args: ("# 本科生院最近三天通知总结\n\n## 摘要\n\n1. **new notice**\n", "body", "<p>body</p>", notices, [notices[0].url]),
        write_summary_file_fn=lambda *_args, **_kwargs: tmp_path / "summary_20260320_evening.md",
        build_email_subject_fn=lambda *_args: "subject",
        send_email_fn=lambda *_args: (_ for _ in ()).throw(RuntimeError("smtp down")),
        send_napcat_message_fn=lambda _settings, target, message: napcat_calls.append((target, message)),
        build_napcat_news_message_fn=lambda markdown, items: f"qq::{len(items)}::{markdown.splitlines()[-1]}",
        save_delivery_record_fn=lambda *args, **kwargs: saved.update({"args": args, "kwargs": kwargs}),
    )

    assert napcat_calls == [("group:123456", "qq::1::1. **new notice**")]
    assert saved["kwargs"]["napcat_sent"] is True
    assert saved["args"][5] is False
    assert saved["args"][6] == "sent"
```

- [ ] **Step 5: Run the targeted workflow tests**

Run: `uv run pytest tests/test_news_service.py tests/test_main.py tests/test_napcat_sender.py -v`
Expected: PASS with evening-only NapCat delivery and per-target error handling verified.

- [ ] **Step 6: Run the focused regression set**

Run: `uv run pytest tests/test_config.py tests/test_delivery_state.py tests/test_napcat_sender.py tests/test_news_service.py tests/test_main.py -v`
Expected: PASS.

### Notes

- Remove or replace temporary AstrBot-specific config, docs, and state names rather than trying to support both channels in the same change.
- Do not add direct AstrBot support in this implementation.
- Do not send course-task or backfill messages to NapCat.
- Do not add git commit steps; the user explicitly asked not to use git for this work.
