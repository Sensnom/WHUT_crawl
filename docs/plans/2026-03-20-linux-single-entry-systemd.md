# Linux Single-Entry Systemd Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep `main.py` as the only runtime entrypoint while refactoring the project for cleaner Linux reuse and `systemd timer` deployment.

**Architecture:** Move orchestration out of `main.py` into focused modules while preserving `python main.py` as the only execution contract. Add mode-based dispatch, a health check flow, and Linux `systemd` scheduler resources under `scheduler/`, while leaving `.env` handling rooted in `config.py` and the project root.

**Tech Stack:** Python 3, argparse, pathlib, pytest, python-dotenv, systemd unit files, Markdown documentation

---

### Task 1: Lock in the new single-entry modes with tests

**Files:**
- Modify: `tests/test_main.py`
- Modify: `main.py`

**Step 1: Write the failing test**

```python
def test_run_dispatches_explicit_news_mode(monkeypatch):
    called = []

    monkeypatch.setattr("main.parse_args", lambda: Namespace(mode="news"))
    monkeypatch.setattr("main.run_news_mode", lambda runtime: called.append("news") or 0)

    assert main() == 0
    assert called == ["news"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_dispatches_explicit_news_mode -v`
Expected: FAIL because `main.py` does not yet expose mode parsing and mode dispatch.

**Step 3: Write minimal implementation**

Add argument parsing and mode dispatch in `main.py` while preserving `python main.py` default behavior.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_dispatches_explicit_news_mode -v`
Expected: PASS.

### Task 2: Extract runtime orchestration out of `main.py`

**Files:**
- Create: `app/runtime.py`
- Create: `app/workflows.py`
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_default_main_mode_still_runs_daily_workflow(monkeypatch):
    called = []
    monkeypatch.setattr("main.parse_args", lambda: Namespace(mode="run"))
    monkeypatch.setattr("main.run_daily_workflow", lambda runtime: called.append("run") or 0)

    assert main() == 0
    assert called == ["run"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_default_main_mode_still_runs_daily_workflow -v`
Expected: FAIL until orchestration is routed through dedicated workflow helpers.

**Step 3: Write minimal implementation**

Introduce a small runtime container and move daily orchestration helpers out of `main.py`, keeping compatibility imports where needed for existing tests.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_default_main_mode_still_runs_daily_workflow -v`
Expected: PASS.

### Task 3: Add health-check coverage before implementing the command

**Files:**
- Modify: `tests/test_main.py`
- Modify: `config.py`
- Modify: `main.py`
- Create: `app/healthcheck.py`

**Step 1: Write the failing test**

```python
def test_healthcheck_mode_reports_missing_browser_dependency(monkeypatch, capsys):
    monkeypatch.setattr("main.parse_args", lambda: Namespace(mode="healthcheck"))
    monkeypatch.setattr("main.run_healthcheck", lambda runtime: 1)

    assert main() == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_healthcheck_mode_reports_missing_browser_dependency -v`
Expected: FAIL because no health-check mode exists yet.

**Step 3: Write minimal implementation**

Add a health-check workflow that validates configuration, output-directory writability, and Playwright browser availability without sending emails.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_healthcheck_mode_reports_missing_browser_dependency -v`
Expected: PASS.

### Task 4: Make settings validation friendlier to partial modes

**Files:**
- Modify: `config.py`
- Modify: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_settings_can_validate_healthcheck_without_mail_credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    settings = Settings.from_env()
    Settings.validate_for_mode(settings, "healthcheck")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_can_validate_healthcheck_without_mail_credentials -v`
Expected: FAIL because validation is not mode-aware yet.

**Step 3: Write minimal implementation**

Keep `Settings.from_env()` behavior stable for the default run, but add explicit mode-aware validation helpers used by mode dispatch and health checks.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_settings_can_validate_healthcheck_without_mail_credentials -v`
Expected: PASS.

### Task 5: Isolate service logic from entrypoint glue

**Files:**
- Create: `services/news_service.py`
- Create: `services/course_service.py`
- Create: `services/backfill_service.py`
- Create: `services/cleanup_service.py`
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_mode_calls_news_and_course_services_independently(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("main.process_news_run", lambda runtime: calls.append("news"))
    monkeypatch.setattr("main.process_course_run", lambda runtime: calls.append("course"))

    assert run() == 0
    assert calls[:2] == ["course", "news"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_run_mode_calls_news_and_course_services_independently -v`
Expected: FAIL because the entrypoint still owns all service logic directly.

**Step 3: Write minimal implementation**

Move workflow-sized functions into service modules and keep `main.py` focused on dispatch and shared error handling.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_run_mode_calls_news_and_course_services_independently -v`
Expected: PASS.

### Task 6: Add Linux `systemd` scheduler resources

**Files:**
- Create: `scheduler/network-crawl.service`
- Create: `scheduler/network-crawl.timer`
- Modify: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
def test_systemd_service_runs_main_from_project_root():
    content = Path("scheduler/network-crawl.service").read_text(encoding="utf-8")
    assert "WorkingDirectory=" in content
    assert "main.py" in content
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py::test_systemd_service_runs_main_from_project_root -v`
Expected: FAIL because the systemd service file does not exist yet.

**Step 3: Write minimal implementation**

Add a oneshot service that runs `main.py` from the project root and a timer that triggers noon and evening runs.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py::test_systemd_service_runs_main_from_project_root -v`
Expected: PASS.

### Task 7: Update README deployment guidance for Linux-first scheduling

**Files:**
- Modify: `README.md`
- Modify: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_readme_mentions_systemd_as_primary_linux_scheduler():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "systemd" in readme
    assert "network-crawl.timer" in readme
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py::test_readme_mentions_systemd_as_primary_linux_scheduler -v`
Expected: FAIL because the README is still cron-first.

**Step 3: Write minimal implementation**

Document `systemd` installation and usage as the primary Linux deployment path while keeping cron as a fallback section.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py::test_readme_mentions_systemd_as_primary_linux_scheduler -v`
Expected: PASS.

### Task 8: Run focused regression checks

**Files:**
- Verify: `tests/test_main.py`
- Verify: `tests/test_config.py`
- Verify: `tests/test_scheduler.py`
- Verify: `tests/test_smoke.py`

**Step 1: Run focused tests**

Run: `pytest tests/test_main.py tests/test_config.py tests/test_scheduler.py tests/test_smoke.py -v`
Expected: PASS.

**Step 2: Run manual entrypoint smoke checks**

Run: `python main.py --mode healthcheck`
Expected: exit code `0` or `1` with clear diagnostics and no email side effects.

**Step 3: Review deployment resources**

Confirm `scheduler/network-crawl.service` and `scheduler/network-crawl.timer` point to `main.py`, preserve project-root execution, and do not embed secrets.
