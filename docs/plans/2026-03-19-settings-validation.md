# Settings Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make invalid environment configuration fail fast with clear validation errors before runtime work begins.

**Architecture:** Keep `Settings` in `config.py`, but split configuration handling into two phases: parse env values into a candidate `Settings` object, then run centralized validation before returning it. Reuse that single validated entrypoint from both `main.py` and `scheduler/manage_cron.py` so cron installation and runtime execution fail consistently.

**Tech Stack:** Python 3.10+, dataclasses, `zoneinfo`, `python-dotenv`, pytest

---

### Task 1: Add failing tests for strict config validation

**Files:**
- Modify: `tests/test_config.py`

**Step 1: Write the failing test**

```python
import pytest


def test_settings_rejects_invalid_schedule_hour(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("SCHEDULE_HOUR", "24")

    with pytest.raises(ValueError, match="SCHEDULE_HOUR"):
        Settings.from_env()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_settings_rejects_invalid_schedule_hour -v`
Expected: FAIL because invalid hours are not currently rejected with a clear config error.

**Step 3: Extend the test set**

Add focused failing tests for:
- non-integer numeric fields such as `REQUEST_TIMEOUT=abc`
- invalid timezone such as `SCHEDULE_TIMEZONE=Asia/Shangha`
- non-positive values such as `MAX_PAGES=0`
- invalid port such as `SMTP_PORT=70000`
- blank `OUTPUT_DIR`

**Step 4: Run focused tests to verify the failures are real**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL only on the new validation expectations.

### Task 2: Add centralized parsing and validation in config

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

**Step 1: Write minimal implementation**

Introduce small helpers inside `config.py` to parse integers with field-aware errors and validate the completed `Settings` object. Keep the code local to `config.py` rather than adding new modules.

```python
def parse_int_env(name: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"配置错误: {name} 必须是整数") from exc


def validate_settings(settings: Settings) -> None:
    errors = []
    if not settings.api_key:
        errors.append("DEEPSEEK_API_KEY 不能为空")
    if not 0 <= settings.schedule_hour <= 23:
        errors.append("SCHEDULE_HOUR 必须是 0-23 的整数")
    ...
    if errors:
        raise ValueError("配置错误: " + "; ".join(errors))
```

**Step 2: Make `Settings.from_env()` use the helpers**

Parse all numeric values through the helper, build the dataclass, run validation, and only then return `settings`.

**Step 3: Run focused tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

### Task 3: Make entrypoints report config failures cleanly

**Files:**
- Modify: `main.py`
- Modify: `scheduler/manage_cron.py`
- Test: `tests/test_scheduler.py`

**Step 1: Add a failing test for the cron entrypoint**

```python
def test_main_returns_error_when_settings_are_invalid(monkeypatch, capsys):
    monkeypatch.setattr(
        "scheduler.manage_cron.Settings.from_env",
        lambda: (_ for _ in ()).throw(ValueError("配置错误: SCHEDULE_HOUR 必须是 0-23 的整数")),
    )

    exit_code = main(["--print"])

    assert exit_code == 1
    assert "配置错误" in capsys.readouterr().out
```

**Step 2: Run the test to verify current behavior**

Run: `uv run pytest tests/test_scheduler.py::test_main_returns_error_when_settings_are_invalid -v`
Expected: PASS already or FAIL only if config errors are not surfaced consistently.

**Step 3: Tighten runtime messaging if needed**

Ensure `main.py` and `scheduler/manage_cron.py` print one concise error line and exit `1` on config failure, without Python tracebacks in normal invalid-config cases.

**Step 4: Run targeted regression tests**

Run: `uv run pytest tests/test_scheduler.py tests/test_config.py -v`
Expected: PASS.

### Task 4: Verify end-to-end strict validation behavior

**Files:**
- Verify: `config.py`
- Verify: `main.py`
- Verify: `scheduler/manage_cron.py`
- Verify: `tests/test_config.py`
- Verify: `tests/test_scheduler.py`

**Step 1: Run focused regression suite**

Run: `uv run pytest tests/test_config.py tests/test_scheduler.py tests/test_main.py -v`
Expected: PASS.

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS.

**Step 3: Review user-facing behavior**

Confirm that invalid `.env` values now fail early with readable field-specific errors and that valid configs continue to load without changing normal delivery behavior.
