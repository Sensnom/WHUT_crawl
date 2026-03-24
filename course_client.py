from collections.abc import Callable
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Protocol

from playwright.sync_api import sync_playwright

from config import Settings


class _PlaywrightBrowser:
    def __init__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)

    def new_page(self, storage_state_path: str | None = None):
        context = self._browser.new_context(storage_state=storage_state_path)
        return context.new_page()

    def close(self):
        self._browser.close()
        self._playwright.stop()


class Browser(Protocol):
    def new_page(self, storage_state_path: str | None = None): ...

    def close(self): ...


LOGIN_URL_MARKERS = (
    "infra.ai-augmented.com/app/auth/oauth2/login",
    "sso.whut.edu.cn",
)
LOGIN_URL_PATTERN = "**/login*"
UNIFIED_IDENTITY_TAB_SELECTOR = "#rc-tabs-0-tab-UnifiedIdentity"
UNIFIED_USERNAME_SELECTOR = "#un"
UNIFIED_PASSWORD_SELECTOR = "#pd"
UNIFIED_SUBMIT_SELECTOR = "#index_login_btn"
UNIFIED_LOGIN_URL_MARKER = "zhlgd.whut.edu.cn/tpass/login"
PENDING_TASK_TRIGGER_SELECTOR = '[data-xy-click-pt="unstudy-task"]'
PENDING_TASK_API_PATH = "/api/jx-stat/group/task/un_finish"
AUTH_STATE_COURSE_WAIT_MS = 5000


class CourseClient:
    def __init__(
        self,
        settings: Settings,
        browser_factory: Callable[[], Browser] | None = None,
    ):
        self.settings = settings
        self.browser_factory = browser_factory or _PlaywrightBrowser

    def fetch_course_page_html(self) -> str:
        browser = self.browser_factory()
        try:
            auth_state_path = self._get_auth_state_path()
            page = browser.new_page(
                str(auth_state_path) if auth_state_path.exists() else None
            )
            timeout_ms = self.settings.request_timeout * 1000
            page.goto(
                self.settings.course_page_url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            if auth_state_path.exists():
                html = self._try_fetch_with_cached_auth_state(page, timeout_ms)
                if html is not None:
                    self._save_auth_state(page, auth_state_path)
                    return html
            if not any(marker in page.url for marker in LOGIN_URL_MARKERS):
                try:
                    page.wait_for_url(LOGIN_URL_PATTERN, timeout=timeout_ms)
                except Exception:
                    pass
            if self._is_infra_login_page(page.url):
                page.click(UNIFIED_IDENTITY_TAB_SELECTOR)
                page.click("button[type='submit']")
                page.wait_for_url("**/tpass/login*", timeout=timeout_ms)

            username_selector, password_selector, submit_selector = (
                self._get_login_controls(page.url)
            )
            page.fill(username_selector, self.settings.smart_whut_username)
            page.fill(password_selector, self.settings.smart_whut_password)
            page.click(submit_selector)
            try:
                page.wait_for_selector("text=待完成任务", timeout=timeout_ms)
            except Exception as exc:
                html = page.content()
                if not self._has_rendered_course_marker(html):
                    raise RuntimeError("课程页面加载失败") from exc
                return html

            html = self._fetch_pending_task_html(page, timeout_ms)
            if not self._has_rendered_course_marker(html):
                raise RuntimeError("课程页面加载失败")
            self._save_auth_state(page, auth_state_path)
            return html
        finally:
            browser.close()

    @classmethod
    def build_pending_task_html(cls, payload: list[dict]) -> str:
        items: list[str] = []
        for task in payload:
            course_name = escape(str(task.get("group_name", "")).strip())
            title = escape(str(task.get("name", "")).strip())
            deadline_text = escape(cls._format_deadline(task.get("end_time")))
            if not course_name or not title or not deadline_text:
                continue
            items.append(
                "".join(
                    [
                        '<div class="task-item">',
                        f'<div class="course-name">{course_name}</div>',
                        f'<div class="task-title">{title}</div>',
                        f'<div class="deadline">截止时间：{deadline_text}</div>',
                        "</div>",
                    ]
                )
            )
        return "<html><body>待完成任务" + "".join(items) + "</body></html>"

    @classmethod
    def _fetch_pending_task_html(self, page, timeout_ms: int) -> str:
        with page.expect_response(
            lambda response: PENDING_TASK_API_PATH in response.url,
            timeout=timeout_ms,
        ) as pending_task_response_info:
            page.click(PENDING_TASK_TRIGGER_SELECTOR)

        response = pending_task_response_info.value
        payload = response.json().get("data", [])
        if isinstance(payload, list) and payload:
            return self.build_pending_task_html(payload)
        return page.content()

    def _try_fetch_with_cached_auth_state(self, page, timeout_ms: int) -> str | None:
        if self._has_course_task_entry(page.content()):
            return self._fetch_pending_task_html(page, timeout_ms)

        try:
            page.wait_for_function(
                """
                () => {
                  const html = document.documentElement?.outerHTML || '';
                  const text = document.body?.innerText || '';
                  return html.includes('data-xy-click-pt="unstudy-task"') ||
                    text.includes('待完成任务') ||
                    window.location.href.includes('/login')
                }
                """,
                timeout=min(timeout_ms, AUTH_STATE_COURSE_WAIT_MS),
            )
        except Exception:
            return None

        if self._has_course_task_entry(page.content()):
            return self._fetch_pending_task_html(page, timeout_ms)
        return None

    def _get_auth_state_path(self) -> Path:
        return Path(self.settings.output_dir) / "playwright_auth_state.json"

    @staticmethod
    def _save_auth_state(page, auth_state_path: Path) -> None:
        auth_state_path.parent.mkdir(parents=True, exist_ok=True)
        page.context.storage_state(path=str(auth_state_path))

    @staticmethod
    def _has_course_task_entry(html: str) -> bool:
        return 'data-xy-click-pt="unstudy-task"' in html or "task-item" in html

    @staticmethod
    def _has_rendered_course_marker(html: str) -> bool:
        return any(marker in html for marker in ("待完成任务", "task-item", "mycourse"))

    @staticmethod
    def _format_deadline(raw_value: object) -> str:
        text = str(raw_value or "").strip()
        if not text:
            return ""
        normalized = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return text

    @staticmethod
    def _get_login_controls(url: str) -> tuple[str, str, str]:
        if UNIFIED_LOGIN_URL_MARKER in url:
            return (
                UNIFIED_USERNAME_SELECTOR,
                UNIFIED_PASSWORD_SELECTOR,
                UNIFIED_SUBMIT_SELECTOR,
            )
        if any(marker in url for marker in LOGIN_URL_MARKERS):
            return "#account", "#password", "button[type='submit']"
        return (
            "input[name='username']",
            "input[name='password']",
            "button[type='submit']",
        )

    @staticmethod
    def _is_infra_login_page(url: str) -> bool:
        return "infra.ai-augmented.com/app/auth/oauth2/login" in url
