# UV Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate this repo from `requirements.txt` + manual `venv` setup to a `uv`-managed workflow with one dependency source of truth.

**Architecture:** Add a minimal `pyproject.toml` for dependency metadata, keep the app as a script-based project, and update docs to use `uv sync` and `uv run`. Use `uv.lock` for reproducible installs and remove `requirements.txt` to avoid split dependency management.

**Tech Stack:** Python 3.10+, uv, PEP 621, pytest, Markdown documentation

---

### Task 1: Add failing tests for uv metadata and docs

**Files:**
- Create: `tests/test_project_metadata.py`
- Modify: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_pyproject_declares_uv_managed_dependencies():
    pyproject = Path("pyproject.toml")
    assert pyproject.exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_metadata.py tests/test_smoke.py::test_readme_documents_uv_workflow -v`
Expected: FAIL because the repo has no `pyproject.toml` and README still documents `pip`.

**Step 3: Write minimal implementation**

Create the new tests for `pyproject.toml` metadata and `uv` README commands.

**Step 4: Run test to verify it fails correctly**

Run: `pytest tests/test_project_metadata.py tests/test_smoke.py::test_readme_documents_uv_workflow -v`
Expected: FAIL for missing metadata/docs, not syntax errors.

### Task 2: Add uv project metadata

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock`
- Delete: `requirements.txt`
- Modify: `.gitignore`
- Test: `tests/test_project_metadata.py`

**Step 1: Write minimal implementation**

Define project metadata, runtime dependencies, and a `dev` dependency group for `pytest`. Add `.venv/` to `.gitignore`, remove `requirements.txt`, and generate `uv.lock`.

**Step 2: Run targeted tests**

Run: `pytest tests/test_project_metadata.py -v`
Expected: PASS.

### Task 3: Update docs to the uv workflow

**Files:**
- Modify: `README.md`
- Test: `tests/test_smoke.py`

**Step 1: Write minimal implementation**

Replace `venv + pip` install steps with `uv sync`, update run/test commands to `uv run`, and keep cron guidance using `.venv/bin/python` for scheduled execution.

**Step 2: Run targeted tests**

Run: `pytest tests/test_smoke.py::test_readme_documents_uv_workflow tests/test_smoke.py::test_readme_documents_gmail_env_fields -v`
Expected: PASS.

### Task 4: Verify the uv workflow end to end

**Files:**
- Verify: `pyproject.toml`
- Verify: `uv.lock`
- Verify: `README.md`

**Step 1: Sync environment**

Run: `uv sync`
Expected: exit 0 and `.venv` created or updated.

**Step 2: Run regression tests**

Run: `uv run pytest tests/test_project_metadata.py tests/test_smoke.py tests/test_config.py tests/test_scheduler.py -v`
Expected: PASS.
