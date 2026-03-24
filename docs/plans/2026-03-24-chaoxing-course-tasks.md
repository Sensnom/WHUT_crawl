# Chaoxing Course Tasks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Chaoxing unfinished assignment and exam crawling for configured courses, then merge those results into the existing Xiaoya course-task notification.

**Architecture:** Keep Xiaoya crawling as-is, add an isolated Chaoxing Playwright client and parser with separate auth-state storage, then aggregate both sources inside `services/course_service.py` before the existing email and artifact flow renders the merged task list.

**Tech Stack:** Python 3.10+, Playwright sync API, dataclasses, pathlib, pytest, Markdown docs

---

### Task 1: Add failing config tests for Chaoxing settings

**Files:**
- Modify: `tests/test_config.py`
- Modify: `config.py`
- Modify: `.env.example`

**Step 1: Write the failing test**

```python
def test_settings_reads_chaoxing_fields(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("CHAOXING_USERNAME", "13800000000")
    monkeypatch.setenv("CHAOXING_PASSWORD", "secret")
    monkeypatch.setenv("CHAOXING_TARGET_COURSE_NAMES", "高数, 大学物理 ")

    settings = Settings.from_env()

    assert settings.chaoxing_username == "13800000000"
    assert settings.chaoxing_password == "secret"
    assert settings.chaoxing_target_course_names == ["高数", "大学物理"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_settings_reads_chaoxing_fields -v`
Expected: FAIL because `Settings` does not expose Chaoxing fields yet.

**Step 3: Write minimal implementation**

Add Chaoxing fields and parsing helpers in `config.py`, then document them in `.env.example`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_settings_reads_chaoxing_fields -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add config.py .env.example tests/test_config.py
git commit -m "feat: add chaoxing settings"
```

### Task 2: Extend the shared course-task model with source metadata

**Files:**
- Modify: `course_parser.py`
- Modify: `tests/test_course_parser.py`

**Step 1: Write the failing test**

```python
def test_parse_pending_course_tasks_defaults_source_and_type():
    html = """
    <div class='task-item'>
      <div class='course-name'>高等数学</div>
      <div class='task-title'>作业 3</div>
      <div class='deadline'>截止时间：2026-03-21 23:59</div>
    </div>
    """

    tasks = parse_pending_course_tasks(html)

    assert tasks[0].source_platform == "xiaoya"
    assert tasks[0].task_type == "task"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_course_parser.py::test_parse_pending_course_tasks_defaults_source_and_type -v`
Expected: FAIL because `CourseTask` has no source metadata yet.

**Step 3: Write minimal implementation**

Extend `CourseTask` with `source_platform` and `task_type`, then set Xiaoya defaults inside `parse_pending_course_tasks()`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_course_parser.py::test_parse_pending_course_tasks_defaults_source_and_type -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add course_parser.py tests/test_course_parser.py
git commit -m "feat: tag course tasks by source"
```

### Task 3: Add failing parser tests for Chaoxing task normalization and filtering

**Files:**
- Create: `chaoxing_parser.py`
- Create: `tests/test_chaoxing_parser.py`

**Step 1: Write the failing test**

```python
from datetime import datetime


def test_parse_chaoxing_items_keeps_unfinished_items_within_30_days():
    from chaoxing_parser import parse_chaoxing_items

    raw_items = [
        {"course_name": "高数", "title": "作业1", "status": "unfinished", "task_type": "assignment", "deadline": "2026-04-10 23:59"},
        {"course_name": "高数", "title": "期中考试", "status": "unfinished", "task_type": "exam", "deadline": "2026-05-30 23:59"},
    ]

    tasks = parse_chaoxing_items(raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"])

    assert [(task.title, task.task_type) for task in tasks] == [("作业1", "assignment")]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_chaoxing_parser.py::test_parse_chaoxing_items_keeps_unfinished_items_within_30_days -v`
Expected: FAIL because the parser module does not exist yet.

**Step 3: Extend the failing test set**

Add focused tests for:
- course-name filtering
- skipping finished items
- skipping entries without parseable deadlines
- keeping `source_platform == "chaoxing"`

**Step 4: Write minimal implementation**

Create `chaoxing_parser.py` with parsing helpers that normalize deadlines, enforce filtering rules, and return shared `CourseTask` objects.

**Step 5: Run targeted tests**

Run: `uv run pytest tests/test_chaoxing_parser.py -v`
Expected: PASS.

**Step 6: Commit**

```bash
git add chaoxing_parser.py tests/test_chaoxing_parser.py
git commit -m "feat: parse chaoxing assignments and exams"
```

### Task 4: Add failing client tests for Chaoxing login reuse and course traversal

**Files:**
- Create: `chaoxing_client.py`
- Create: `tests/test_chaoxing_client.py`

**Step 1: Write the failing test**

```python
def test_fetch_chaoxing_tasks_reuses_saved_auth_state(tmp_path):
    from chaoxing_client import ChaoxingClient

    auth_state_path = tmp_path / "chaoxing_auth_state.json"
    auth_state_path.write_text("{}", encoding="utf-8")

    page = FakeChaoxingPage(course_names=["高数"], assignments=[], exams=[])
    browser = FakeBrowser(page)
    client = ChaoxingClient(make_settings_with_output(tmp_path), browser_factory=lambda: browser)

    client.fetch_pending_tasks()

    assert browser.new_page_storage_paths == [str(auth_state_path)]
    assert page.fills == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_chaoxing_client.py::test_fetch_chaoxing_tasks_reuses_saved_auth_state -v`
Expected: FAIL because the Chaoxing client and fake page harness do not exist yet.

**Step 3: Extend the failing test set**

Add focused tests that verify:
- login happens when cached auth is missing
- only configured course names are entered
- both assignment and exam sections are visited
- raw task payloads from both sections are returned

**Step 4: Write minimal implementation**

Create `chaoxing_client.py` with isolated selectors, auth-state persistence, course selection, and section traversal helpers.

**Step 5: Run targeted tests**

Run: `uv run pytest tests/test_chaoxing_client.py -v`
Expected: PASS.

**Step 6: Commit**

```bash
git add chaoxing_client.py tests/test_chaoxing_client.py
git commit -m "feat: crawl chaoxing course tasks"
```

### Task 5: Add failing service tests for Xiaoya and Chaoxing aggregation

**Files:**
- Modify: `services/course_service.py`
- Modify: `tests/test_course_service.py`
- Modify: `main.py`

**Step 1: Write the failing test**

```python
def test_fetch_course_tasks_merges_xiaoya_and_chaoxing_results(tmp_path):
    settings = make_settings(tmp_path)
    settings.chaoxing_target_course_names = ["高数"]

    tasks = fetch_course_tasks(
        settings,
        course_client_factory=lambda _settings: FakeXiaoyaClient(),
        chaoxing_client_factory=lambda _settings: FakeChaoxingClient(),
    )

    assert [task.source_platform for task in tasks] == ["xiaoya", "chaoxing"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_course_service.py::test_fetch_course_tasks_merges_xiaoya_and_chaoxing_results -v`
Expected: FAIL because the service does not aggregate Chaoxing yet.

**Step 3: Extend the failing test set**

Add focused tests that verify:
- Chaoxing skips cleanly when credentials or target courses are missing
- Xiaoya failure still returns Chaoxing tasks
- Chaoxing failure still returns Xiaoya tasks
- both failures raise a delivery error that preserves current behavior

**Step 4: Write minimal implementation**

Update `services/course_service.py` so `fetch_course_tasks()` aggregates both sources and returns a merged list plus optional warnings that can be rendered into the outgoing artifact and email.

Update `main.py` wiring so the production path passes `CourseClient` and `ChaoxingClient` into the service.

**Step 5: Run targeted tests**

Run: `uv run pytest tests/test_course_service.py -v`
Expected: PASS.

**Step 6: Commit**

```bash
git add services/course_service.py tests/test_course_service.py main.py
git commit -m "feat: merge xiaoya and chaoxing tasks"
```

### Task 6: Add failing email-rendering tests for grouped merged output

**Files:**
- Modify: `email_sender.py`
- Modify: `tests/test_email_sender.py`

**Step 1: Write the failing test**

```python
def test_build_course_task_email_body_groups_tasks_by_platform_and_type():
    tasks = [
        CourseTask(title="作业1", course_name="高数", deadline_text="2026-03-25 23:59", source_platform="xiaoya", task_type="task"),
        CourseTask(title="实验报告", course_name="大物", deadline_text="2026-03-26 23:59", source_platform="chaoxing", task_type="assignment"),
        CourseTask(title="单元测试", course_name="大物", deadline_text="2026-03-27 23:59", source_platform="chaoxing", task_type="exam"),
    ]

    body = build_course_task_email_body(tasks)

    assert "小雅" in body
    assert "超星学习通 / 作业" in body
    assert "超星学习通 / 考试" in body
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_email_sender.py::test_build_course_task_email_body_groups_tasks_by_platform_and_type -v`
Expected: FAIL because the renderer does not group merged sources yet.

**Step 3: Write minimal implementation**

Update the plain-text and HTML course-task renderers in `email_sender.py` to group tasks by source and type while preserving the existing empty-state behavior.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_email_sender.py::test_build_course_task_email_body_groups_tasks_by_platform_and_type -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add email_sender.py tests/test_email_sender.py
git commit -m "feat: group merged course task emails"
```

### Task 7: Document the new Chaoxing configuration and merged notification behavior

**Files:**
- Modify: `README.md`
- Modify: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_readme_documents_chaoxing_course_task_settings():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "CHAOXING_USERNAME" in readme
    assert "CHAOXING_TARGET_COURSE_NAMES" in readme
    assert "和小雅的任务放在同一封课程任务邮件里" in readme
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_smoke.py::test_readme_documents_chaoxing_course_task_settings -v`
Expected: FAIL because the README does not describe Chaoxing integration yet.

**Step 3: Write minimal implementation**

Update `README.md` to explain:
- new `.env` fields
- one-month unfinished assignment/exam filtering
- configured-course-name matching
- merged Xiaoya plus Chaoxing delivery behavior

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_smoke.py::test_readme_documents_chaoxing_course_task_settings -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add README.md tests/test_smoke.py
git commit -m "docs: document chaoxing task integration"
```

### Task 8: Run focused and full regression checks

**Files:**
- Verify: `config.py`
- Verify: `course_parser.py`
- Verify: `chaoxing_parser.py`
- Verify: `chaoxing_client.py`
- Verify: `services/course_service.py`
- Verify: `email_sender.py`
- Verify: `README.md`
- Verify: `tests/test_config.py`
- Verify: `tests/test_course_parser.py`
- Verify: `tests/test_chaoxing_parser.py`
- Verify: `tests/test_chaoxing_client.py`
- Verify: `tests/test_course_service.py`
- Verify: `tests/test_email_sender.py`
- Verify: `tests/test_smoke.py`

**Step 1: Run focused tests**

Run: `uv run pytest tests/test_config.py tests/test_course_parser.py tests/test_chaoxing_parser.py tests/test_chaoxing_client.py tests/test_course_service.py tests/test_email_sender.py tests/test_smoke.py -v`
Expected: PASS.

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS.

**Step 3: Commit**

```bash
git add docs/plans/2026-03-24-chaoxing-course-tasks-design.md docs/plans/2026-03-24-chaoxing-course-tasks.md
git commit -m "docs: plan chaoxing course task integration"
```
