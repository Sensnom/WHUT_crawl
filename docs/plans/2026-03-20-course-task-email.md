# Course Task Email Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a second daily email that logs into the Smart WHUT course site, extracts unfinished tasks and deadlines, and sends a separate course-task reminder email alongside the existing news email.

**Architecture:** Keep `main.py` as the single scheduler entrypoint, but split delivery into two independent pipelines: news delivery and course-task delivery. Add a session-based course client for SSO login, a parser for the `mycourse` page, and separate delivery-state keys so failures and retries stay isolated per email type.

**Tech Stack:** Python 3, requests, BeautifulSoup, python-dotenv, pytest, smtplib

---

### Task 1: Add course site configuration

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
def test_settings_reads_course_site_credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("COURSE_PAGE_URL", "https://whut.ai-augmented.com/app/jx-web/mycourse")
    monkeypatch.setenv("SMART_WHUT_USERNAME", "2020123456")
    monkeypatch.setenv("SMART_WHUT_PASSWORD", "secret")

    settings = Settings.from_env()

    assert settings.course_page_url == "https://whut.ai-augmented.com/app/jx-web/mycourse"
    assert settings.smart_whut_username == "2020123456"
    assert settings.smart_whut_password == "secret"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_settings_reads_course_site_credentials -v`
Expected: FAIL because the config fields do not exist yet.

**Step 3: Write minimal implementation**

Add new `Settings` fields and load them from `.env`:

```python
course_page_url: str = "https://whut.ai-augmented.com/app/jx-web/mycourse"
smart_whut_username: str = ""
smart_whut_password: str = ""
```

Update `.env.example` with the three new variables.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_settings_reads_course_site_credentials -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add config.py .env.example tests/test_config.py
git commit -m "feat: add course site configuration"
```

### Task 2: Parse unfinished course tasks from course HTML

**Files:**
- Create: `course_parser.py`
- Create: `tests/test_course_parser.py`

**Step 1: Write the failing test**

```python
def test_parse_pending_course_tasks_extracts_title_course_and_deadline():
    html = """
    <div class="task-item">
      <div class="course-name">高等数学</div>
      <div class="task-title">作业 3</div>
      <div class="deadline">截止时间：2026-03-21 23:59</div>
    </div>
    """

    tasks = parse_pending_course_tasks(html)

    assert len(tasks) == 1
    assert tasks[0].course_name == "高等数学"
    assert tasks[0].title == "作业 3"
    assert tasks[0].deadline_text == "2026-03-21 23:59"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_course_parser.py::test_parse_pending_course_tasks_extracts_title_course_and_deadline -v`
Expected: FAIL because the parser module does not exist.

**Step 3: Write minimal implementation**

Create `course_parser.py` with:

```python
@dataclass
class CourseTask:
    title: str
    course_name: str
    deadline_text: str
    deadline_at: datetime | None = None
    url: str = ""


def parse_pending_course_tasks(html: str) -> list[CourseTask]:
    ...
```

Implement the smallest parser that can extract tasks from the current HTML fixture.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_course_parser.py::test_parse_pending_course_tasks_extracts_title_course_and_deadline -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add course_parser.py tests/test_course_parser.py
git commit -m "feat: parse pending course tasks"
```

### Task 3: Add course email subject and body builders

**Files:**
- Modify: `email_sender.py`
- Modify: `tests/test_email_sender.py`

**Step 1: Write the failing test**

```python
def test_build_course_task_email_body_includes_tasks_and_deadlines():
    tasks = [
        CourseTask(
            title="作业 3",
            course_name="高等数学",
            deadline_text="2026-03-21 23:59",
        )
    ]

    body = build_course_task_email_body(tasks)

    assert "高等数学" in body
    assert "作业 3" in body
    assert "2026-03-21 23:59" in body
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_email_sender.py::test_build_course_task_email_body_includes_tasks_and_deadlines -v`
Expected: FAIL because the builder does not exist.

**Step 3: Write minimal implementation**

Add:

```python
def build_course_task_email_subject(target_date: datetime, slot: str) -> str:
    ...


def build_course_task_email_body(tasks: list[CourseTask]) -> str:
    ...


def build_course_task_email_html(tasks: list[CourseTask]) -> str:
    ...
```

If `tasks` is empty, produce a message containing `今日没有待完成任务`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_email_sender.py::test_build_course_task_email_body_includes_tasks_and_deadlines -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add email_sender.py tests/test_email_sender.py
git commit -m "feat: add course task email builders"
```

### Task 4: Log into the course page through Smart WHUT SSO

**Files:**
- Create: `course_client.py`
- Create: `tests/test_course_client.py`

**Step 1: Write the failing test**

```python
def test_fetch_course_page_submits_login_form_and_returns_page_html():
    client = CourseClient(...)
    html = client.fetch_course_page_html()
    assert "待完成任务" in html
```
```

Use a fake session in the test that:
- first returns a redirect/login page
- then accepts a POST to the login form
- then returns the final `mycourse` page HTML

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_course_client.py::test_fetch_course_page_submits_login_form_and_returns_page_html -v`
Expected: FAIL because the client does not exist.

**Step 3: Write minimal implementation**

Create a `CourseClient` that:
- owns a `requests.Session`
- requests `settings.course_page_url`
- detects the Smart WHUT login form
- parses action URL and hidden inputs
- submits `SMART_WHUT_USERNAME` and `SMART_WHUT_PASSWORD`
- re-fetches or follows through to the final course page HTML

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_course_client.py::test_fetch_course_page_submits_login_form_and_returns_page_html -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add course_client.py tests/test_course_client.py
git commit -m "feat: add Smart WHUT course login client"
```

### Task 5: Add a course-task delivery path to the scheduler entrypoint

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_run_sends_news_and_course_task_emails_in_same_run(monkeypatch, tmp_path):
    sent = []
    ...
    monkeypatch.setattr("main.send_email", fake_send_email)
    monkeypatch.setattr("main.fetch_course_tasks", lambda settings: [])

    assert run() == 0
    assert len(sent) == 2
```
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py::test_run_sends_news_and_course_task_emails_in_same_run -v`
Expected: FAIL because `run()` currently only sends the news email path.

**Step 3: Write minimal implementation**

Add a course delivery function to `main.py` that:
- fetches course page HTML
- parses tasks
- builds the course-task email
- sends the course-task email
- records its own delivery status

Then call it from the noon/evening runtime path without merging it into the news email.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py::test_run_sends_news_and_course_task_emails_in_same_run -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: send separate daily course task email"
```

### Task 6: Send an explicit empty course-task email when no tasks exist

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_email_sender.py`

**Step 1: Write the failing test**

```python
def test_run_sends_empty_course_task_email_when_no_tasks(monkeypatch, tmp_path):
    sent = {"subjects": [], "bodies": []}
    ...
    monkeypatch.setattr("main.fetch_course_tasks", lambda settings: [])

    assert run() == 0
    assert any("课程任务提醒" in subject for subject in sent["subjects"])
    assert any("今日没有待完成任务" in body for body in sent["bodies"])
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py::test_run_sends_empty_course_task_email_when_no_tasks -v`
Expected: FAIL until empty-result delivery is implemented.

**Step 3: Write minimal implementation**

Ensure the course-task delivery path always sends a course email, even for `[]`, using the empty-state body and HTML builders.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py::test_run_sends_empty_course_task_email_when_no_tasks -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py tests/test_email_sender.py
git commit -m "feat: send empty course task reminders"
```

### Task 7: Isolate course-task delivery state from news delivery state

**Files:**
- Modify: `delivery_state.py`
- Modify: `main.py`
- Modify: `tests/test_delivery_state.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_news_and_course_task_deliveries_keep_separate_state_records(tmp_path):
    store = DeliveryStateStore(...)
    ...
    assert store.get_record("2026-03-20", "noon") is not None
    assert store.get_record("2026-03-20", "course_tasks_noon") is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_delivery_state.py::test_news_and_course_task_deliveries_keep_separate_state_records -v`
Expected: FAIL because course-task slots are not represented yet.

**Step 3: Write minimal implementation**

Either:
- extend `DeliveryRecord.slot` usage to accept `course_tasks_noon` / `course_tasks_evening`, or
- add a `kind` field if that proves cleaner with the current code.

Use the smaller change that preserves current behavior with minimal migration risk.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_delivery_state.py::test_news_and_course_task_deliveries_keep_separate_state_records -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add delivery_state.py main.py tests/test_delivery_state.py tests/test_main.py
git commit -m "feat: track course task deliveries separately"
```

### Task 8: Keep one pipeline failing from blocking the other

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_course_task_failure_does_not_block_news_email(monkeypatch, tmp_path):
    sent = {"count": 0}
    ...
    monkeypatch.setattr("main.fetch_course_tasks", failing_fetch)
    monkeypatch.setattr("main.send_email", fake_send_email)

    assert run() == 0
    assert sent["count"] >= 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py::test_course_task_failure_does_not_block_news_email -v`
Expected: FAIL if one pipeline exception aborts the whole run.

**Step 3: Write minimal implementation**

Wrap the course-task pipeline in its own exception handling so a login/parse/send failure does not abort the news pipeline, and vice versa.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py::test_course_task_failure_does_not_block_news_email -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "fix: isolate course task delivery failures"
```

### Task 9: Document course task email setup

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Test: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_readme_documents_course_task_email_setup():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "SMART_WHUT_USERNAME" in readme
    assert "课程任务邮件" in readme
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_smoke.py::test_readme_documents_course_task_email_setup -v`
Expected: FAIL until the documentation is updated.

**Step 3: Write minimal implementation**

Update `README.md` to describe:
- new `.env` settings
- that each send window produces two emails
- that the second email comes from Smart WHUT course tasks
- that an empty-state course email is still sent

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_smoke.py::test_readme_documents_course_task_email_setup -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add README.md .env.example tests/test_smoke.py
git commit -m "docs: describe course task email branch"
```

### Task 10: Run the delivery regression suite

**Files:**
- Modify: none

**Step 1: Write the failing test**

No new test code. Use the full delivery-related regression suite.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py tests/test_delivery_state.py tests/test_email_sender.py tests/test_course_parser.py tests/test_course_client.py -v`
Expected: Any failures must be understood and fixed before completion.

**Step 3: Write minimal implementation**

No new implementation. Only fix regressions caused by the feature work.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py tests/test_delivery_state.py tests/test_email_sender.py tests/test_course_parser.py tests/test_course_client.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add .
git commit -m "test: verify course task email delivery flow"
```
