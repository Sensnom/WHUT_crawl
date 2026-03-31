from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urlparse
import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import Settings
from course_parser import CourseTask
from chaoxing_parser import parse_chaoxing_items


CHAOXING_LOGIN_URL = (
    "https://passport2.chaoxing.com/login?"
    "fid=12&refer=http%3A%2F%2Fi.chaoxing.com%2Fbase%3Fws%3D1&space=2"
)
CHAOXING_BASE_URL = "https://i.chaoxing.com/base?ws=1"


class _PlaywrightBrowser:
    def __init__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)

    def new_page(self, storage_state_path: str | None = None):
        context = self._browser.new_context(
            storage_state=storage_state_path,
            viewport={"width": 1280, "height": 900},
        )
        return context.new_page()

    def close(self):
        self._browser.close()
        self._playwright.stop()


class Browser(Protocol):
    def new_page(self, storage_state_path: str | None = None): ...
    def close(self): ...


class ChaoxingClient:
    def __init__(
        self,
        settings: Settings,
        browser_factory: Callable[[], Browser] | None = None,
    ):
        self.settings = settings
        self.browser_factory = browser_factory or _PlaywrightBrowser

    def _get_auth_state_path(self) -> Path:
        return Path(self.settings.output_dir) / "chaoxing_auth_state.json"

    def fetch_pending_tasks(self) -> tuple[list[CourseTask], list[str]]:
        browser = self.browser_factory()
        try:
            auth_state_path = self._get_auth_state_path()
            page = browser.new_page(
                str(auth_state_path) if auth_state_path.exists() else None
            )
            timeout_ms = self.settings.request_timeout * 1000

            self._login_if_needed(page, timeout_ms, auth_state_path)

            tasks, warnings = self._crawl_courses(page, timeout_ms)

            if auth_state_path.exists():
                self._save_auth_state(page, auth_state_path)

            return tasks, warnings
        finally:
            browser.close()

    def _login_if_needed(self, page, timeout_ms: int, auth_state_path: Path) -> None:
        page.goto(CHAOXING_LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        if "/login" in page.url.lower():
            self._perform_login(page, timeout_ms)
            self._save_auth_state(page, auth_state_path)

    def _perform_login(self, page, timeout_ms: int) -> None:
        page.wait_for_selector("input[placeholder='手机号/超星号']", timeout=timeout_ms)
        page.fill(
            "input[placeholder='手机号/超星号']",
            self.settings.chaoxing_username,
        )
        page.fill(
            "input[placeholder='学习通密码']",
            self.settings.chaoxing_password,
        )
        page.click("button[type='button'].btn-big-blue")
        try:
            page.wait_for_url("**/i.chaoxing.com/base**", timeout=timeout_ms)
        except Exception:
            pass
        page.wait_for_timeout(3000)

    def _save_auth_state(self, page, auth_state_path: Path) -> None:
        auth_state_path.parent.mkdir(parents=True, exist_ok=True)
        page.context.storage_state(path=str(auth_state_path))

    def _crawl_courses(
        self, page, timeout_ms: int
    ) -> tuple[list[CourseTask], list[str]]:
        warnings: list[str] = []
        all_tasks: list[CourseTask] = []
        now = datetime.now()
        target_names = self.settings.chaoxing_target_course_names

        course_links = self._find_target_course_links(page, target_names)

        if not course_links and target_names:
            warnings.append(
                f"未在超星找到目标课程: {', '.join(target_names)}。"
                "请检查课程名称是否与超星平台显示一致。"
            )

        for course_name, course_url, course_params in course_links:
            try:
                tasks = self._crawl_single_course(
                    page, course_name, course_url, course_params, timeout_ms, now
                )
                all_tasks.extend(tasks)
            except Exception as exc:
                warnings.append(f"课程「{course_name}」爬取失败: {exc}")

        return all_tasks, warnings

    def _find_target_course_links(
        self, page, target_names: list[str]
    ) -> list[tuple[str, str, dict]]:
        links: list[tuple[str, str, dict]] = []
        if not target_names:
            return links

        page.wait_for_url("**/i.chaoxing.com/base**", timeout=15000)
        page.wait_for_timeout(3000)

        frame = page.frame_locator('iframe[src*="mooc1"]')
        for a in frame.locator('a[href*="stucoursemiddle"]').all():
            name = (a.inner_text() or "").strip()
            href = a.get_attribute("href") or ""
            if not name or not href:
                continue
            if any(name == tn or name.startswith(tn) for tn in target_names):
                links.append((name, href, {}))

        return links

    def _crawl_single_course(
        self,
        page,
        course_name: str,
        course_url: str,
        course_params: dict,
        timeout_ms: int,
        now: datetime,
    ) -> list[CourseTask]:
        page.goto(course_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(3000)

        parsed = urlparse(page.url)
        qs = parse_qs(parsed.query)
        courseid = qs.get("courseId", [""])[0]
        clazzid = qs.get("clazzid", [""])[0]
        cpi = qs.get("cpi", [""])[0]
        enc = qs.get("enc", [""])[0]

        raw_items: list[dict] = []

        raw_items.extend(self._get_work_items(page, courseid, clazzid, cpi, enc))
        raw_items.extend(self._get_exam_items(page, courseid, clazzid, cpi, enc))

        return parse_chaoxing_items(raw_items, now, [course_name])

    def _get_work_items(
        self, page, courseid: str, clazzid: str, cpi: str, enc: str
    ) -> list[dict]:
        items: list[dict] = []
        try:
            page.goto(
                f"{page.url.split('?')[0].replace('/studentcourse', '')}"
                or f"https://mooc1-2.chaoxing.com/visit/stucoursemiddle?courseid={courseid}&clazzid={clazzid}&vc=1&cpi={cpi}",
                timeout=20000,
            )
            page.wait_for_timeout(2000)
            page.locator("a:has-text('作业')").first.click()
            page.wait_for_timeout(3000)

            soup = BeautifulSoup(page.content(), "html.parser")
            for li in soup.select(".ulDiv ul li"):
                title_el = li.select_one(".titTxt a[title]")
                if not title_el:
                    continue
                title = title_el.get("title", "").strip() or title_el.get_text(
                    strip=True
                )
                if not title:
                    continue

                text = li.get_text()
                deadline = ""

                dl = re.search(
                    r"截止时间[：:]\s*(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})", text
                )
                if dl:
                    deadline = dl.group(1).strip()

                status = ""
                if "已完成" in text or "已提交" in text:
                    status = "finished"
                elif "未完成" in text or "待做" in text:
                    status = "unfinished"
                else:
                    continue

                items.append(
                    {
                        "course_name": "",
                        "title": title,
                        "status": status,
                        "task_type": "assignment",
                        "deadline": deadline,
                        "url": "",
                    }
                )
        except Exception:
            pass
        return items

    def _get_exam_items(
        self, page, courseid: str, clazzid: str, cpi: str, enc: str
    ) -> list[dict]:
        items: list[dict] = []
        try:
            page.goto(
                f"https://mooc1-2.chaoxing.com/exam-ans/exam/test?"
                f"classId={clazzid}&courseid={courseid}&cpi={cpi}&enc={enc}",
                timeout=20000,
            )
            page.wait_for_timeout(3000)

            soup = BeautifulSoup(page.content(), "html.parser")
            for row in soup.select("table.line_table tbody tr, .examList .item"):
                cells = row.select("td")
                if len(cells) < 3:
                    continue

                title_el = row.select_one("a[href*='test'], .tit")
                status_el = cells[-2] if len(cells) >= 2 else None
                deadline_el = cells[-1] if cells else None

                title = ""
                if title_el:
                    title = (
                        title_el.get("title", "") or title_el.get_text(strip=True)
                    ).strip()

                if not title:
                    continue

                text = row.get_text()
                status = "unfinished"
                if "已完成" in text or "已结束" in text or "已考" in text:
                    status = "finished"
                elif "未开始" in text:
                    status = "upcoming"

                deadline = ""
                dl_match = re.search(
                    r"(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})",
                    deadline_el.get_text() if deadline_el else "",
                )
                if dl_match:
                    deadline = dl_match.group(1).strip()

                items.append(
                    {
                        "course_name": "",
                        "title": title,
                        "status": status,
                        "task_type": "exam",
                        "deadline": deadline,
                        "url": "",
                    }
                )
        except Exception:
            pass
        return items
