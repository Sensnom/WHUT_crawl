# Daily Email Cron Installer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a safe, repeatable cron installer so this project can schedule the existing daily email pipeline without requiring the user to hand-edit `crontab`.

**Architecture:** Keep `main.py` as the only runtime entrypoint and add a small `scheduler/manage_cron.py` module that builds a managed cron block, replaces that block idempotently inside the current user's crontab, and can also remove or print it. Load schedule defaults from `config.py` so docs, tests, and runtime behavior stay aligned.

**Tech Stack:** Python 3, argparse, subprocess, pathlib, python-dotenv, pytest

---

### Task 1: Add schedule settings to config

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_settings_reads_schedule_fields(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("SCHEDULE_TIMEZONE", "Asia/Shanghai")
    monkeypatch.setenv("SCHEDULE_HOUR", "9")
    monkeypatch.setenv("SCHEDULE_MINUTE", "30")
    settings = Settings.from_env()
    assert settings.schedule_timezone == "Asia/Shanghai"
    assert settings.schedule_hour == 9
    assert settings.schedule_minute == 30
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_reads_schedule_fields -v`
Expected: FAIL because schedule settings do not exist yet.

**Step 3: Write minimal implementation**

Add `schedule_timezone`, `schedule_hour`, and `schedule_minute` to `Settings`, load them in `Settings.from_env()`, and document them in `.env.example`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_settings_reads_schedule_fields -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add config.py .env.example tests/test_config.py
git commit -m "feat: add daily schedule settings"
```

### Task 2: Build managed cron text helpers

**Files:**
- Create: `scheduler/manage_cron.py`
- Create: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
def test_build_managed_cron_block_uses_settings_values(tmp_path):
    block = build_managed_cron_block(
        project_root=tmp_path,
        python_bin="/usr/bin/python3",
        timezone="Asia/Shanghai",
        hour=8,
        minute=0,
    )
    assert "# BEGIN network_crawl daily email" in block
    assert "TZ=Asia/Shanghai" in block
    assert "0 8 * * * /usr/bin/python3" in block
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py::test_build_managed_cron_block_uses_settings_values -v`
Expected: FAIL because the module does not exist yet.

**Step 3: Write minimal implementation**

Create helper functions that validate hour/minute and return a managed cron block with markers, timezone, `main.py`, and `output/cron.log` paths.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py::test_build_managed_cron_block_uses_settings_values -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scheduler/manage_cron.py tests/test_scheduler.py
git commit -m "feat: generate managed daily cron block"
```

### Task 3: Make cron installation idempotent

**Files:**
- Modify: `scheduler/manage_cron.py`
- Test: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
def test_upsert_managed_block_replaces_previous_block():
    existing = "# BEGIN network_crawl daily email\nold\n# END network_crawl daily email\n"
    updated = upsert_managed_block(existing, "new")
    assert updated.count("# BEGIN network_crawl daily email") == 1
    assert "new" in updated
    assert "old" not in updated
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py::test_upsert_managed_block_replaces_previous_block -v`
Expected: FAIL because replacement logic does not exist yet.

**Step 3: Write minimal implementation**

Add helpers to insert a managed block when absent, replace it when present, and preserve unrelated cron lines.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py::test_upsert_managed_block_replaces_previous_block -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scheduler/manage_cron.py tests/test_scheduler.py
git commit -m "feat: upsert managed cron block safely"
```

### Task 4: Support removing the managed cron block

**Files:**
- Modify: `scheduler/manage_cron.py`
- Test: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
def test_remove_managed_block_keeps_other_cron_entries():
    existing = "MAILTO=a@example.com\n# BEGIN network_crawl daily email\njob\n# END network_crawl daily email\n0 1 * * * echo hi\n"
    updated = remove_managed_block(existing)
    assert "network_crawl daily email" not in updated
    assert "MAILTO=a@example.com" in updated
    assert "0 1 * * * echo hi" in updated
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py::test_remove_managed_block_keeps_other_cron_entries -v`
Expected: FAIL because removal logic does not exist yet.

**Step 3: Write minimal implementation**

Add a helper that strips only the managed block and leaves all other cron content unchanged.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py::test_remove_managed_block_keeps_other_cron_entries -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scheduler/manage_cron.py tests/test_scheduler.py
git commit -m "feat: remove managed cron block"
```

### Task 5: Add CLI install, print, and remove commands

**Files:**
- Modify: `scheduler/manage_cron.py`
- Test: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
def test_main_print_outputs_managed_block(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("scheduler.manage_cron.get_project_root", lambda: tmp_path)
    exit_code = main(["--print"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "# BEGIN network_crawl daily email" in out
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py::test_main_print_outputs_managed_block -v`
Expected: FAIL because the CLI entrypoint does not exist yet.

**Step 3: Write minimal implementation**

Implement an `argparse` CLI with mutually exclusive `--print`, `--install`, and `--remove` flags. For install/remove, read the current crontab with `crontab -l`, transform it, then write back with `crontab -`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scheduler/manage_cron.py tests/test_scheduler.py
git commit -m "feat: add cron management cli"
```

### Task 6: Document the new setup flow

**Files:**
- Modify: `README.md`
- Modify: `scheduler/cron.example`
- Test: `tests/test_smoke.py`

**Step 1: Write the failing test**

Add a docs regression test that checks `README.md` mentions `SCHEDULE_TIMEZONE` and `python scheduler/manage_cron.py --install`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL until the setup flow is documented.

**Step 3: Write minimal implementation**

Update docs to explain:
- configure `.env`
- run `python main.py` once manually
- install daily cron with `python scheduler/manage_cron.py --install`
- remove with `python scheduler/manage_cron.py --remove`

Refresh `scheduler/cron.example` so it matches the managed block format.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add README.md scheduler/cron.example tests/test_smoke.py
git commit -m "docs: add managed daily cron setup"
```

### Task 7: Verify the full feature

**Files:**
- Modify: none

**Step 1: Write the failing test**

No new automated test. Use the completed suite as regression coverage and run the CLI in print mode for manual verification.

**Step 2: Run test to verify it fails**

Not applicable.

**Step 3: Write minimal implementation**

No code changes.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py tests/test_scheduler.py tests/test_smoke.py -v`
Expected: PASS.

Run: `python scheduler/manage_cron.py --print`
Expected: prints one managed cron block with timezone and daily execution command.

**Step 5: Commit**

```bash
git add README.md config.py .env.example scheduler/manage_cron.py tests/test_config.py tests/test_scheduler.py tests/test_smoke.py scheduler/cron.example
git commit -m "feat: add daily email cron installer"
```
