from config import Settings
from course_parser import parse_pending_course_tasks
from pathlib import Path


class FakePage:
    def __init__(
        self,
        rendered_html: str,
        url: str = "https://whut.ai-augmented.com/app/jx-web/mycourse",
    ):
        self.rendered_html = rendered_html
        self.url = url
        self.visited_urls: list[str] = []
        self.fills: list[tuple[str, str]] = []
        self.clicked_selectors: list[str] = []
        self.waited_selectors: list[tuple[str, int]] = []
        self.waited_urls: list[tuple[str, int]] = []
        self.next_url: str | None = None
        self.click_url_updates: dict[str, str] = {}
        self.pending_task_payload: list[dict] = []
        self.saved_storage_paths: list[str] = []
        self.deferred_html: str | None = None

    def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None):
        self.visited_urls.append(url)

    def fill(self, selector: str, value: str):
        self.fills.append((selector, value))

    def click(self, selector: str):
        self.clicked_selectors.append(selector)
        if selector in self.click_url_updates:
            self.url = self.click_url_updates[selector]

    def wait_for_selector(self, selector: str, timeout: int):
        self.waited_selectors.append((selector, timeout))

    def wait_for_url(self, url_pattern: str, timeout: int):
        self.waited_urls.append((url_pattern, timeout))
        if self.next_url is not None:
            self.url = self.next_url
            self.next_url = None

    def content(self) -> str:
        return self.rendered_html

    def expect_response(self, predicate, timeout: int):
        return FakeResponseContext(self.pending_task_payload)

    @property
    def context(self):
        return self

    def storage_state(self, path: str):
        self.saved_storage_paths.append(path)

    def wait_for_function(self, script: str, timeout: int):
        if self.deferred_html is not None:
            self.rendered_html = self.deferred_html
            self.deferred_html = None


class FakeResponse:
    def __init__(self, payload: list[dict]):
        self.url = "https://whut.ai-augmented.com/api/jx-stat/group/task/un_finish"
        self._payload = payload

    def json(self) -> dict:
        return {"data": self._payload}


class FakeResponseContext:
    def __init__(self, payload: list[dict]):
        self.value = FakeResponse(payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeBrowser:
    def __init__(self, page: FakePage):
        self.page = page
        self.closed = False
        self.new_page_storage_paths: list[str | None] = []

    def new_page(self, storage_state_path: str | None = None) -> FakePage:
        self.new_page_storage_paths.append(storage_state_path)
        return self.page

    def close(self):
        self.closed = True


def make_settings() -> Settings:
    return Settings(
        api_key="k",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        request_timeout=60,
        course_page_url="https://whut.ai-augmented.com/app/jx-web/mycourse",
        smart_whut_username="2020123456",
        smart_whut_password="secret",
    )


def make_settings_with_output(tmp_path: Path) -> Settings:
    settings = make_settings()
    settings.output_dir = str(tmp_path)
    return settings


def test_fetch_course_page_uses_browser_login_and_returns_rendered_html():
    from course_client import CourseClient

    page = FakePage("<html><body><div>待完成任务</div></body></html>")
    browser = FakeBrowser(page)
    client = CourseClient(make_settings(), browser_factory=lambda: browser)

    html = client.fetch_course_page_html()

    assert "待完成任务" in html
    assert page.visited_urls == ["https://whut.ai-augmented.com/app/jx-web/mycourse"]
    assert page.fills == [
        ("input[name='username']", "2020123456"),
        ("input[name='password']", "secret"),
    ]
    assert page.clicked_selectors == [
        "button[type='submit']",
        '[data-xy-click-pt="unstudy-task"]',
    ]
    assert page.waited_selectors == [("text=待完成任务", 60000)]
    assert browser.closed is True


def test_fetch_course_page_supports_real_login_page_selectors():
    from course_client import CourseClient

    page = FakePage(
        "<html><body><div>待完成任务</div></body></html>",
        url="https://infra.ai-augmented.com/app/auth/oauth2/login",
    )
    browser = FakeBrowser(page)
    client = CourseClient(make_settings(), browser_factory=lambda: browser)

    html = client.fetch_course_page_html()

    assert "待完成任务" in html
    assert page.fills == [
        ("#account", "2020123456"),
        ("#password", "secret"),
    ]


def test_fetch_course_page_uses_login_controls_detected_from_dom_when_url_is_unexpected():
    from course_client import CourseClient

    page = FakePage(
        "<html><body><input id='account'><input id='password'><div>待完成任务</div></body></html>",
        url="https://whut.ai-augmented.com/app/jx-web/mycourse",
    )
    browser = FakeBrowser(page)
    client = CourseClient(make_settings(), browser_factory=lambda: browser)

    html = client.fetch_course_page_html()

    assert "待完成任务" in html
    assert page.fills == [
        ("#account", "2020123456"),
        ("#password", "secret"),
    ]


def test_fetch_course_page_waits_for_redirected_login_page_before_filling():
    from course_client import CourseClient

    page = FakePage("<html><body><div>待完成任务</div></body></html>")
    page.next_url = "https://infra.ai-augmented.com/app/auth/oauth2/login"
    page.click_url_updates = {
        "button[type='submit']": "https://zhlgd.whut.edu.cn/tpass/login",
        "#index_login_btn": "https://whut.ai-augmented.com/app/jx-web/mycourse",
    }
    browser = FakeBrowser(page)
    client = CourseClient(make_settings(), browser_factory=lambda: browser)

    client.fetch_course_page_html()

    assert page.waited_urls == [("**/login*", 60000), ("**/tpass/login*", 60000)]
    assert page.clicked_selectors[:2] == [
        "#rc-tabs-0-tab-UnifiedIdentity",
        "button[type='submit']",
    ]
    assert page.fills == [("#un", "2020123456"), ("#pd", "secret")]


def test_fetch_course_page_uses_unified_identity_flow_for_school_account():
    from course_client import CourseClient

    page = FakePage(
        "<html><body><div>待完成任务</div></body></html>",
        url="https://infra.ai-augmented.com/app/auth/oauth2/login",
    )
    page.click_url_updates = {
        "button[type='submit']": "https://zhlgd.whut.edu.cn/tpass/login",
        "#index_login_btn": "https://whut.ai-augmented.com/app/jx-web/mycourse",
    }
    browser = FakeBrowser(page)
    client = CourseClient(make_settings(), browser_factory=lambda: browser)

    html = client.fetch_course_page_html()

    assert "待完成任务" in html
    assert page.clicked_selectors[:2] == [
        "#rc-tabs-0-tab-UnifiedIdentity",
        "button[type='submit']",
    ]
    assert page.fills == [
        ("#un", "2020123456"),
        ("#pd", "secret"),
    ]
    assert page.clicked_selectors[-2:] == [
        "#index_login_btn",
        '[data-xy-click-pt="unstudy-task"]',
    ]


def test_fetch_course_page_raises_when_rendered_course_marker_never_appears():
    from course_client import CourseClient

    page = FakePage("<html><body>登录失败</body></html>")
    client = CourseClient(make_settings(), browser_factory=lambda: FakeBrowser(page))

    try:
        client.fetch_course_page_html()
    except RuntimeError as exc:
        assert str(exc) == "课程页面加载失败"
    else:
        raise AssertionError(
            "Expected RuntimeError when no rendered course marker appears"
        )


def test_build_pending_task_html_from_api_payload():
    from course_client import CourseClient

    payload = [
        {
            "group_name": "数字电子技术基础B",
            "name": "第2章作业",
            "end_time": "2026-03-22T15:59:59.999Z",
        }
    ]

    html = CourseClient.build_pending_task_html(payload)
    tasks = parse_pending_course_tasks(html)

    assert len(tasks) == 1
    assert tasks[0].course_name == "数字电子技术基础B"
    assert tasks[0].title == "第2章作业"
    assert tasks[0].deadline_text == "2026-03-22 15:59"


def test_fetch_course_page_reuses_saved_auth_state_without_relogin(tmp_path: Path):
    from course_client import CourseClient

    auth_state_path = tmp_path / "playwright_auth_state.json"
    auth_state_path.write_text("{}", encoding="utf-8")

    page = FakePage(
        '<html><body><div data-xy-click-pt="unstudy-task">待完成任务</div></body></html>'
    )
    page.pending_task_payload = []
    browser = FakeBrowser(page)
    client = CourseClient(
        make_settings_with_output(tmp_path), browser_factory=lambda: browser
    )

    html = client.fetch_course_page_html()

    assert "待完成任务" in html
    assert browser.new_page_storage_paths == [str(auth_state_path)]
    assert page.fills == []
    assert page.saved_storage_paths == [str(auth_state_path)]


def test_fetch_course_page_refreshes_auth_state_after_fallback_relogin(tmp_path: Path):
    from course_client import CourseClient

    auth_state_path = tmp_path / "playwright_auth_state.json"
    auth_state_path.write_text("{}", encoding="utf-8")

    page = FakePage(
        "<html><body><div>待完成任务</div></body></html>",
        url="https://infra.ai-augmented.com/app/auth/oauth2/login",
    )
    page.click_url_updates = {
        "button[type='submit']": "https://zhlgd.whut.edu.cn/tpass/login",
        "#index_login_btn": "https://whut.ai-augmented.com/app/jx-web/mycourse",
    }
    browser = FakeBrowser(page)
    client = CourseClient(
        make_settings_with_output(tmp_path), browser_factory=lambda: browser
    )

    client.fetch_course_page_html()

    assert browser.new_page_storage_paths == [str(auth_state_path)]
    assert page.fills == [("#un", "2020123456"), ("#pd", "secret")]
    assert page.saved_storage_paths == [str(auth_state_path)]


def test_fetch_course_page_waits_briefly_for_cached_course_dom_before_relogin(
    tmp_path: Path,
):
    from course_client import CourseClient

    auth_state_path = tmp_path / "playwright_auth_state.json"
    auth_state_path.write_text("{}", encoding="utf-8")

    page = FakePage("<html><body>加载中</body></html>")
    page.deferred_html = '<html><body><div data-xy-click-pt="unstudy-task">待完成任务</div></body></html>'
    browser = FakeBrowser(page)
    client = CourseClient(
        make_settings_with_output(tmp_path), browser_factory=lambda: browser
    )

    html = client.fetch_course_page_html()

    assert "待完成任务" in html
    assert page.fills == []
    assert browser.new_page_storage_paths == [str(auth_state_path)]
