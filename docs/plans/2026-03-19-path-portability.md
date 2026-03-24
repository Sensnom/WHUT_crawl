# Path Portability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove hardcoded filesystem paths from runtime-facing templates and docs so the project can be moved to any checkout directory without editing code.

**Architecture:** Keep runtime path discovery rooted in `Path(__file__).resolve()` and `scheduler/manage_cron.py` so the code computes real paths dynamically. Replace hardcoded absolute paths in examples with portable placeholders and add tests that lock in the new documentation/template behavior.

**Tech Stack:** Python 3, pathlib, argparse, pytest, Markdown documentation

---

### Task 1: Lock in a portable cron template

**Files:**
- Modify: `scheduler/cron.example`
- Test: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
def test_cron_example_uses_portable_placeholders():
    content = Path("scheduler/cron.example").read_text(encoding="utf-8")
    assert "<PROJECT_ROOT>" in content
    assert "/home/Sparkle" not in content
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py::test_cron_example_uses_portable_placeholders -v`
Expected: FAIL because the template still contains an absolute path.

**Step 3: Write minimal implementation**

Replace absolute path examples with `<PROJECT_ROOT>` placeholders while keeping the cron block shape intact.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py::test_cron_example_uses_portable_placeholders -v`
Expected: PASS.

### Task 2: Lock in portable README examples

**Files:**
- Modify: `README.md`
- Test: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_readme_does_not_hardcode_local_absolute_paths():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "/home/Sparkle" not in readme
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py::test_readme_does_not_hardcode_local_absolute_paths -v`
Expected: FAIL because the README still includes a machine-specific cron example.

**Step 3: Write minimal implementation**

Rewrite the cron example and surrounding guidance to use `<PROJECT_ROOT>` and recommend `scheduler/manage_cron.py --print` for generating machine-specific entries.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py::test_readme_does_not_hardcode_local_absolute_paths -v`
Expected: PASS.

### Task 3: Verify dynamic cron generation still works

**Files:**
- Modify: `tests/test_scheduler.py`
- Verify: `scheduler/manage_cron.py`

**Step 1: Write the failing test**

```python
def test_build_managed_cron_block_uses_dynamic_project_root(tmp_path):
    block = build_managed_cron_block(...)
    assert str(tmp_path / "main.py") in block
    assert str(tmp_path / "output" / "cron.log") in block
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py::test_build_managed_cron_block_uses_dynamic_project_root -v`
Expected: PASS already or FAIL only if a regression exists.

**Step 3: Write minimal implementation**

Only adjust code if the current helper is not already dynamic.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS.

### Task 4: Run regression checks

**Files:**
- Verify: `tests/test_scheduler.py`
- Verify: `tests/test_smoke.py`
- Verify: `tests/test_config.py`

**Step 1: Run focused tests**

Run: `pytest tests/test_scheduler.py tests/test_smoke.py tests/test_config.py -v`
Expected: PASS.

**Step 2: Review changed files**

Confirm the repo no longer documents any local absolute path while runtime path discovery still works from any checkout directory.
