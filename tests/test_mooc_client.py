from datetime import datetime
from unittest.mock import MagicMock

from config import Settings
from mooc_client import (
    MOOC_HOME_URL,
    MOOC_LOGIN_URL,
    MoocClient,
    _clean_mooc_task_title,
    _is_mooc_task_within_window,
    _parse_mooc_deadline,
)


class FakeMoocLoginPage:
    def __init__(self, landing_url: str, rendered_html: str = ""):
        self.url = "about:blank"
        self._landing_url = landing_url
        self._rendered_html = rendered_html
        self.visited_urls: list[str] = []
        self._goto_count = 0

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.visited_urls.append(url)
        assert url == MOOC_LOGIN_URL
        self._goto_count += 1
        if self._goto_count == 1:
            self.url = self._landing_url
        else:
            self.url = MOOC_LOGIN_URL

    def wait_for_timeout(self, timeout_ms: int) -> None:
        if "logingate/changeCookie" in self.url:
            self.url = "https://www.icourse163.org/"

    def content(self) -> str:
        return self._rendered_html


class FakeMoocPopupPage:
    def __init__(self, url: str):
        self.url = url
        self.closed = False

    def wait_for_load_state(self, state: str) -> None:
        assert state == "domcontentloaded"

    def close(self) -> None:
        self.closed = True


class FakeMoocExpectPage:
    def __init__(self, page: "FakeMoocCoursePage"):
        self._page = page

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    @property
    def value(self) -> FakeMoocPopupPage:
        if self._page.pending_popup_url is None:
            raise RuntimeError("no popup opened")
        return FakeMoocPopupPage(self._page.pending_popup_url)


class FakeMoocContext:
    def __init__(self, page: "FakeMoocCoursePage"):
        self._page = page

    def expect_page(self, timeout: int) -> FakeMoocExpectPage:
        assert timeout == 3000
        return FakeMoocExpectPage(self._page)


class FakeMoocLocator:
    def __init__(
        self, page: "FakeMoocCoursePage", selector: str, index: int | None = None
    ):
        self._page = page
        self._selector = selector
        self._index = index

    @property
    def first(self) -> "FakeMoocLocator":
        return FakeMoocLocator(self._page, self._selector, 0)

    def nth(self, index: int) -> "FakeMoocLocator":
        return FakeMoocLocator(self._page, self._selector, index)

    def count(self) -> int:
        if self._selector == 'a[href="#/home/course"]':
            return 1
        if self._selector == "a.j-course-card-box":
            return len(self._page.card_popup_urls)
        return 0

    def click(self, timeout: int | None = None) -> None:
        if self._selector == 'a[href="#/home/course"]':
            return
        if self._selector == "a.j-course-card-box":
            if self._index is None:
                raise RuntimeError("card index required")
            self._page.pending_popup_url = self._page.card_popup_urls[self._index]
            return
        raise AssertionError(f"unexpected click selector: {self._selector}")


class FakeMoocCoursePage:
    def __init__(
        self,
        home_html: str,
        card_popup_urls: list[str],
        course_pages: dict[str, tuple[str, str]],
    ):
        self.url = MOOC_HOME_URL
        self._home_html = home_html
        self._current_html = home_html
        self.card_popup_urls = card_popup_urls
        self.course_pages = course_pages
        self.pending_popup_url: str | None = None
        self.visited_urls: list[str] = []

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.visited_urls.append(url)
        if url in self.course_pages:
            actual_url, html = self.course_pages[url]
            self.url = actual_url
            self._current_html = html
            return
        self.url = url
        self._current_html = self._home_html

    def wait_for_timeout(self, timeout_ms: int) -> None:
        return None

    def evaluate(self, script: str) -> None:
        return None

    def content(self) -> str:
        return self._current_html

    def locator(self, selector: str) -> FakeMoocLocator:
        return FakeMoocLocator(self, selector)

    @property
    def context(self) -> FakeMoocContext:
        return FakeMoocContext(self)


def test_login_if_needed_skips_relogin_during_change_cookie_redirect():
    settings = MagicMock(spec=Settings)
    client = MoocClient(settings)
    page = FakeMoocLoginPage(
        "https://www.icourse163.org/passport/logingate/changeCookie.htm?type=study"
    )
    client._perform_login = MagicMock()

    client._login_if_needed(page, timeout_ms=30000)

    client._perform_login.assert_not_called()


def test_login_if_needed_retries_real_login_when_homepage_is_still_logged_out():
    settings = MagicMock(spec=Settings)
    client = MoocClient(settings)
    page = FakeMoocLoginPage(
        "https://www.icourse163.org/home.htm",
        rendered_html="<html><body>登录 | 注册</body></html>",
    )
    client._perform_login = MagicMock()

    client._login_if_needed(page, timeout_ms=30000)

    assert page.visited_urls == [MOOC_LOGIN_URL, MOOC_LOGIN_URL]
    client._perform_login.assert_called_once_with(page, 30000)


def test_login_if_needed_retries_real_login_when_auth_state_lands_on_logout():
    settings = MagicMock(spec=Settings)
    client = MoocClient(settings)
    page = FakeMoocLoginPage(
        "https://www.icourse163.org/passport/member/logout.htm?lgoutp=1"
    )
    client._perform_login = MagicMock()

    client._login_if_needed(page, timeout_ms=30000)

    assert page.visited_urls == [MOOC_LOGIN_URL, MOOC_LOGIN_URL]
    client._perform_login.assert_called_once_with(page, 30000)


def test_get_mooc_courses_discovers_cards_without_href_by_opening_them():
    settings = MagicMock(spec=Settings)
    client = MoocClient(settings)
    key = "WHUT-1001862004"
    course_url = f"https://www.icourse163.org/learn/{key}"
    popup_url = f"{course_url}?tid=1476735447#/learn/announce"
    page = FakeMoocCoursePage(
        home_html="<html><body><a class='j-course-card-box'>数字电路01密码的奥秘</a></body></html>",
        card_popup_urls=[popup_url],
        course_pages={
            course_url: (
                popup_url,
                "<html><head><title>数字电路01密码的奥秘_中国大学MOOC(慕课)</title></head><body></body></html>",
            )
        },
    )

    courses = client._get_mooc_courses(page, timeout_ms=30000)

    assert courses == [
        {
            "name": "数字电路01密码的奥秘",
            "key": key,
            "term_id": "1476735447",
            "url": course_url,
            "is_spoc": False,
        }
    ]


def test_clean_mooc_task_title_removes_ui_noise_and_keeps_core_name():
    assert (
        _clean_mooc_task_title(
            "时间：2026/05/03 23:30前往测验请注意作业",
            "时间：2026/05/03 23:30前往测验请注意作业",
            "assignment",
        )
        == "作业"
    )


def test_parse_mooc_deadline_parses_slash_datetime_text():
    text, dt = _parse_mooc_deadline(
        "时间：2026/05/03 23:30前往测验", datetime(2026, 4, 11, 12, 0)
    )

    assert text == "2026-05-03 23:30"
    assert dt == datetime(2026, 5, 3, 23, 30)


def test_is_mooc_task_within_window_keeps_only_next_30_days():
    now = datetime(2026, 4, 11, 12, 0)

    assert _is_mooc_task_within_window(datetime(2026, 5, 3, 23, 30), now) is True
    assert _is_mooc_task_within_window(datetime(2026, 4, 1, 23, 30), now) is False
    assert _is_mooc_task_within_window(datetime(2026, 5, 20, 23, 30), now) is False
