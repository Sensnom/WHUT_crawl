# Course Task Playwright Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Smart WHUT course-task fetch path with a Playwright-based browser flow so the project can log in and extract JS-rendered course tasks reliably.

**Architecture:** Keep the existing scheduler, parser, and email pipeline structure. Swap the course client implementation from `requests` to a Playwright-backed browser client, keep `fetch_course_tasks()` as the single integration point, and document the new runtime dependency.

**Tech Stack:** Python 3, Playwright, BeautifulSoup, pytest, python-dotenv

---

### Task 1: Add Playwright dependency

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_project_metadata.py`

**Step 1: Write the failing test**

```python
def test_project_declares_playwright_dependency():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'playwright>=' in text
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_project_metadata.py::test_project_declares_playwright_dependency -v`
Expected: FAIL because Playwright is not declared yet.

**Step 3: Write minimal implementation**

Add `playwright>=1.52.0` to the main dependencies list in `pyproject.toml`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_project_metadata.py::test_project_declares_playwright_dependency -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml tests/test_project_metadata.py
git commit -m "feat: add playwright dependency for course login"
```

### Task 2: Make course client browser-driven

**Files:**
- Modify: `course_client.py`
- Modify: `tests/test_course_client.py`

**Step 1: Write the failing test**

```python
def test_fetch_course_page_uses_browser_login_and_returns_rendered_html():
    page = FakePage(...)
    client = CourseClient(settings, browser_factory=lambda: FakeBrowser(page))

    html = client.fetch_course_page_html()

    assert "待完成任务" in html
    assert page.fills == [
        ("input[name='username']", "2020123456"),
        ("input[name='password']", "secret"),
    ]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_course_client.py::test_fetch_course_page_uses_browser_login_and_returns_rendered_html -v`
Expected: FAIL because the current client is `requests`-based and has no browser abstraction.

**Step 3: Write minimal implementation**

Refactor `CourseClient` to:
- create a browser/page object through an injectable factory
- open `settings.course_page_url`
- fill username/password fields
- submit the login form
- wait for the rendered course page marker
- return `page.content()`

Keep the production path thin; only add enough abstraction to test the flow.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_course_client.py::test_fetch_course_page_uses_browser_login_and_returns_rendered_html -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add course_client.py tests/test_course_client.py
git commit -m "feat: use playwright for Smart WHUT course login"
```

### Task 3: Fail clearly when login never reaches a rendered course page

**Files:**
- Modify: `course_client.py`
- Modify: `tests/test_course_client.py`

**Step 1: Write the failing test**

```python
def test_fetch_course_page_raises_when_rendered_course_marker_never_appears():
    page = FakePage(rendered_html="<html><body>登录失败</body></html>")
    client = CourseClient(settings, browser_factory=lambda: FakeBrowser(page))

    with pytest.raises(RuntimeError, match="课程页面加载失败"):
        client.fetch_course_page_html()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_course_client.py::test_fetch_course_page_raises_when_rendered_course_marker_never_appears -v`
Expected: FAIL because the client does not validate the final page yet.

**Step 3: Write minimal implementation**

After returning rendered HTML, verify it contains either a known task-area marker or another explicit course-page marker. If not, raise `RuntimeError("课程页面加载失败")`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_course_client.py::test_fetch_course_page_raises_when_rendered_course_marker_never_appears -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add course_client.py tests/test_course_client.py
git commit -m "fix: detect Smart WHUT render failures"
```

### Task 4: Keep course task fetch integration stable

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

```python
def test_fetch_course_tasks_parses_rendered_html_from_course_client(monkeypatch):
    monkeypatch.setattr("main.CourseClient", FakeCourseClient)

    tasks = fetch_course_tasks(settings)

    assert len(tasks) == 1
    assert tasks[0].title == "作业 3"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py::test_fetch_course_tasks_parses_rendered_html_from_course_client -v`
Expected: FAIL until the integration test reflects the browser-backed client path.

**Step 3: Write minimal implementation**

Keep `fetch_course_tasks()` as the stable integration point. Adjust only what is necessary so it still delegates to `CourseClient.fetch_course_page_html()` and `parse_pending_course_tasks()`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py::test_fetch_course_tasks_parses_rendered_html_from_course_client -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "test: lock course client integration to rendered html"
```

### Task 5: Document Playwright runtime setup

**Files:**
- Modify: `README.md`
- Modify: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_readme_documents_playwright_install_for_course_tasks():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "uv add playwright" in readme or "playwright install" in readme
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_smoke.py::test_readme_documents_playwright_install_for_course_tasks -v`
Expected: FAIL because README does not mention Playwright setup yet.

**Step 3: Write minimal implementation**

Update `README.md` to explain:
- the course task branch now depends on Playwright
- first-time setup requires browser installation
- cron/deployment machines need the browser runtime too

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_smoke.py::test_readme_documents_playwright_install_for_course_tasks -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add README.md tests/test_smoke.py
git commit -m "docs: describe playwright setup for course tasks"
```

### Task 6: Run focused browser-course regression suite

**Files:**
- Modify: none

**Step 1: Write the failing test**

No new test code. Use the focused suite for the browser-backed course task flow.

**Step 2: Run test to verify current status**

Run: `uv run pytest tests/test_course_client.py tests/test_course_parser.py tests/test_main.py tests/test_email_sender.py -v`
Expected: Any failures must be understood and fixed before completion.

**Step 3: Write minimal implementation**

No new feature code. Fix only regressions introduced by the Playwright migration.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_course_client.py tests/test_course_parser.py tests/test_main.py tests/test_email_sender.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add .
git commit -m "test: verify browser-based course task delivery flow"
```
