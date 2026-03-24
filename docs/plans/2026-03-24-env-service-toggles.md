# Env Service Toggles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `.env` switches that independently enable or disable the news service and the course-task service.

**Architecture:** Keep configuration parsing in `config.py` and gate service execution in `app/workflows.py`, where the runtime already sequences cleanup, retries, backfill, course delivery, and news delivery. Use two boolean settings with safe defaults so existing deployments stay unchanged unless the new env vars are set.

**Tech Stack:** Python 3.10+, dataclasses, `python-dotenv`, pytest, Markdown documentation

---

### Task 1: Add failing tests for boolean service toggles in config

**Files:**
- Modify: `tests/test_config.py`
- Modify: `config.py`

**Step 1: Write the failing test**

```python
def test_settings_enable_both_services_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    settings = Settings.from_env()

    assert settings.enable_news_service is True
    assert settings.enable_course_service is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_settings_enable_both_services_by_default -v`
Expected: FAIL because the settings object does not yet expose these fields.

**Step 3: Extend the test set**

Add focused tests for:
- `ENABLE_NEWS_SERVICE=false` disables only the news flag
- `ENABLE_COURSE_SERVICE=0` disables only the course flag
- invalid values such as `ENABLE_NEWS_SERVICE=maybe` raise a clear config error

**Step 4: Run focused tests to verify the failures are real**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL only on the new toggle expectations.

### Task 2: Implement env boolean parsing and settings fields

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

**Step 1: Write minimal implementation**

Add a small boolean parser in `config.py`, extend `Settings` with `enable_news_service` and `enable_course_service`, and parse the two env vars with `true` defaults.

```python
def parse_bool_env(name: str, raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"配置错误: {name} 必须是布尔值")
```

**Step 2: Make `Settings.from_env()` use the helper**

Load both env vars through the new parser and keep defaults at `true`.

**Step 3: Run focused tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

### Task 3: Lock in workflow behavior when news is disabled

**Files:**
- Modify: `tests/test_main.py`
- Modify: `app/workflows.py`

**Step 1: Write the failing test**

```python
def test_run_skips_all_news_steps_when_news_service_is_disabled(monkeypatch, tmp_path):
    calls = []
    settings = make_settings(tmp_path)
    settings.enable_news_service = False

    monkeypatch.setattr("main.load_settings_for_mode", lambda mode: settings)
    monkeypatch.setattr("main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0))
    monkeypatch.setattr("main.retry_failed_deliveries_for_today", lambda *_args: calls.append("retry") or set())
    monkeypatch.setattr("main.send_backfill_if_needed", lambda *_args: calls.append("backfill"))
    monkeypatch.setattr("main.process_news_run", lambda runtime: calls.append("news"))

    assert run() == 0
    assert calls == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py::test_run_skips_all_news_steps_when_news_service_is_disabled -v`
Expected: FAIL because the workflow still runs news retry, backfill, and send logic unconditionally.

**Step 3: Write minimal implementation**

Gate all news-specific orchestration in `app/workflows.py` behind `runtime.settings.enable_news_service`, including retry, backfill, slot-driven news sending, and any news-only skip message.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py::test_run_skips_all_news_steps_when_news_service_is_disabled -v`
Expected: PASS.

### Task 4: Lock in workflow behavior when course service is disabled

**Files:**
- Modify: `tests/test_main.py`
- Modify: `app/workflows.py`

**Step 1: Write the failing test**

```python
def test_run_skips_course_delivery_when_course_service_is_disabled(monkeypatch, tmp_path):
    calls = []
    settings = make_settings(tmp_path)
    settings.enable_course_service = False

    monkeypatch.setattr("main.load_settings_for_mode", lambda mode: settings)
    monkeypatch.setattr("main.get_current_time", lambda _settings: datetime(2026, 3, 19, 12, 0))
    monkeypatch.setattr("main.process_course_run", lambda runtime: calls.append("course"))
    monkeypatch.setattr("main.process_news_run", lambda runtime: calls.append("news"))

    assert run() == 0
    assert calls == ["news"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py::test_run_skips_course_delivery_when_course_service_is_disabled -v`
Expected: FAIL because course delivery still runs unconditionally.

**Step 3: Write minimal implementation**

Gate `runtime.process_course_run(runtime)` behind `runtime.settings.enable_course_service` while preserving normal news execution.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py::test_run_skips_course_delivery_when_course_service_is_disabled -v`
Expected: PASS.

### Task 5: Document the new env switches

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

**Step 1: Write the failing documentation checks**

Add or extend lightweight tests if the repo already validates docs/examples; otherwise make the doc update part of manual verification.

**Step 2: Write minimal documentation**

Add the new env vars to `.env.example` and explain in `README.md` that:
- both default to enabled
- turning off news disables retries, backfill, and news delivery together
- turning off course service disables course-task emails only

**Step 3: Review docs for consistency**

Confirm variable names and default values match `config.py` exactly.

### Task 6: Run focused regression checks

**Files:**
- Verify: `config.py`
- Verify: `app/workflows.py`
- Verify: `README.md`
- Verify: `.env.example`
- Verify: `tests/test_config.py`
- Verify: `tests/test_main.py`

**Step 1: Run focused tests**

Run: `uv run pytest tests/test_config.py tests/test_main.py -v`
Expected: PASS.

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS.

**Step 3: Manually review mixed-mode behavior**

Confirm these scenarios are covered by tests or explicit spot checks:
- both services enabled
- news disabled, course enabled
- news enabled, course disabled
- both services disabled
