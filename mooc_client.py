"""
MOOC客户端 - 中国大学MOOC/SPOC课程任务抓取
支持作业和考试截止时间提醒

通过Playwright直接操作MOOC的SPA页面，点击作业/考试标签来加载动态内容
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import Settings
from course_parser import CourseTask


MOOC_LOGIN_URL = "https://www.icourse163.org/member/login.htm"
MOOC_HOME_URL = "https://www.icourse163.org/home.htm"
MOOC_COURSE_LEARN_URL = "https://www.icourse163.org/learn/{course_key}"
SPOC_COURSE_LEARN_URL = "https://www.icourse163.org/spoc/learn/{course_key}"


class Browser(Protocol):
    def new_page(self, storage_state_path: str | None = None): ...
    def close(self): ...


class _PlaywrightBrowser:
    def __init__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)

    def new_page(self, storage_state_path: str | None = None):
        context_options = {"viewport": {"width": 1280, "height": 900}}

        if storage_state_path and Path(storage_state_path).exists():
            context_options["storage_state"] = storage_state_path

        context = self._browser.new_context(**context_options)
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        """)

        return context.new_page()

    def close(self):
        self._browser.close()
        self._playwright.stop()


class MoocClient:
    def __init__(
        self,
        settings: Settings,
        browser_factory: Callable[[], Browser] | None = None,
    ):
        self.settings = settings
        self.browser_factory = browser_factory or _PlaywrightBrowser

    def _get_auth_state_path(self) -> Path:
        return Path(self.settings.output_dir) / "mooc_auth_state.json"

    def fetch_pending_tasks(self) -> tuple[list[CourseTask], list[str]]:
        browser = self.browser_factory()
        warnings: list[str] = []
        all_tasks: list[CourseTask] = []
        now = datetime.now()

        try:
            auth_state_path = self._get_auth_state_path()
            page = browser.new_page(
                str(auth_state_path) if auth_state_path.exists() else None
            )
            timeout_ms = self.settings.request_timeout * 1000

            self._login_if_needed(page, timeout_ms)

            enrolled_courses = self._get_enrolled_courses(page, timeout_ms)

            if not enrolled_courses:
                warnings.append(
                    "未找到任何已注册的MOOC/SPOC课程。"
                    "MOOC平台可能需要您先在网页上参加课程。"
                )
                return [], warnings

            target_names = self.settings.mooc_target_course_names
            if target_names:
                enrolled_courses = [
                    c
                    for c in enrolled_courses
                    if any(name in c["name"] for name in target_names)
                ]
                if not enrolled_courses:
                    warnings.append(
                        f"未在MOOC/SPOC找到目标课程: {', '.join(target_names)}。"
                        "请检查课程名称是否与平台显示一致。"
                        "注意：MOOC课程名称格式为「课程名_学校名」，"
                        "SPOC课程可能有不同的URL格式。"
                    )

            if not enrolled_courses:
                return [], warnings

            print(f"[MOOC] 发现 {len(enrolled_courses)} 门课程:")
            for c in enrolled_courses:
                print(
                    f"  - {c['name']} (key: {c['key']}, is_spoc: {c.get('is_spoc', False)})"
                )

            for course in enrolled_courses:
                try:
                    tasks = self._crawl_single_course(page, course, timeout_ms, now)
                    all_tasks.extend(tasks)
                except Exception as exc:
                    warnings.append(f"课程「{course['name']}」爬取失败: {exc}")

            if not all_tasks:
                warnings.append(
                    "MOOC/SPOC课程页面为动态加载的SPA应用，作业/考试数据通过JavaScript异步获取。"
                    "由于MOOC平台的反爬限制，可能无法获取到作业和考试信息。"
                    '建议：1) 在网页端确认课程有作业/考试 2) 课程需要处于"进行中"状态'
                )

            if auth_state_path.exists():
                self._save_auth_state(page, auth_state_path)

            return all_tasks, warnings

        finally:
            browser.close()

    def _login_if_needed(self, page, timeout_ms: int) -> None:
        page.goto(MOOC_LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        if "login" in page.url.lower():
            self._perform_login(page, timeout_ms)

    def _perform_login(self, page, timeout_ms: int) -> None:
        try:
            phone_tab_selectors = [
                "li:has-text('手机号登录')",
                "li:has-text('手机登录')",
                ".last-login-holder:has-text('手机')",
            ]
            for selector in phone_tab_selectors:
                try:
                    tab = page.locator(selector).first
                    if tab.is_visible():
                        tab.click()
                        break
                except Exception:
                    pass
        except Exception:
            pass

        page.wait_for_timeout(3000)

        frame = self._find_login_frame(page)

        email_input = self._find_email_input(frame)
        email_input.fill(self.settings.mooc_email)
        time.sleep(0.3)

        password_input = self._find_password_input(frame)
        password_input.fill(self.settings.mooc_password)
        time.sleep(0.3)

        login_button = self._find_login_button(frame)
        login_button.click()

        try:
            page.wait_for_url("**/home.htm**", timeout=15000)
        except Exception:
            pass

        page.wait_for_timeout(3000)

    def _find_login_frame(self, page) -> object:
        frame_selectors = [
            "#j-ursContainer-1 iframe",
            "iframe[id*='URS-iframe']",
            "iframe[src*='index_dl2']",
        ]

        for selector in frame_selectors:
            try:
                frames = page.frame_locator(selector)
                test_locator = frames.locator("input[type='password']").first
                test_locator.wait_for(timeout=2000)
                if test_locator.is_visible():
                    return frames
            except Exception:
                pass

        for i in range(page.locator("iframe").count()):
            try:
                frame = page.frame_locator("iframe").nth(i)
                test_locator = frame.locator(
                    "input[type='tel'], input[type='password']"
                ).first
                test_locator.wait_for(timeout=1000)
                return frame
            except Exception:
                pass

        raise RuntimeError("未找到登录iframe")

    def _find_email_input(self, frame) -> object:
        selectors = [
            "input[type='tel']",
            "input.dlemail.j-nameforslide",
            "input[name='email']",
            "input[placeholder*='手机']",
        ]
        for selector in selectors:
            try:
                locator = frame.locator(selector).first
                locator.wait_for(timeout=2000)
                if locator.is_visible():
                    return locator
            except Exception:
                pass
        raise RuntimeError("未找到手机号输入框")

    def _find_password_input(self, frame) -> object:
        selectors = [
            "input.dlpwd",
            "input[type='password']",
            "input[placeholder*='密码']",
        ]
        for selector in selectors:
            try:
                locator = frame.locator(selector).first
                locator.wait_for(timeout=2000)
                if locator.is_visible():
                    return locator
            except Exception:
                pass
        raise RuntimeError("未找到密码输入框")

    def _find_login_button(self, frame) -> object:
        selectors = [
            "a#submitBtn",
            "a.u-loginbtn",
            "a:has-text('登录')",
            "button[type='submit']",
        ]
        for selector in selectors:
            try:
                locator = frame.locator(selector).first
                locator.wait_for(timeout=2000)
                if locator.is_visible():
                    return locator
            except Exception:
                pass
        raise RuntimeError("未找到登录按钮")

    def _save_auth_state(self, page, auth_state_path: Path) -> None:
        auth_state_path.parent.mkdir(parents=True, exist_ok=True)
        page.context.storage_state(path=str(auth_state_path))

    def _get_enrolled_courses(self, page, timeout_ms: int) -> list[dict]:
        page.goto(MOOC_HOME_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(5000)

        courses: list[dict] = []

        try:
            self._close_modals(page)
        except Exception:
            pass

        mooc_courses = self._get_mooc_courses(page, timeout_ms)
        courses.extend(mooc_courses)

        try:
            self._close_modals(page)
        except Exception:
            pass

        spoc_courses = self._get_spoc_courses(page, timeout_ms)
        courses.extend(spoc_courses)

        return courses

    def _close_modals(self, page) -> None:
        try:
            page.locator(".ant-modal-close").first.click(timeout=1000)
            page.wait_for_timeout(500)
        except Exception:
            pass

        try:
            page.locator('[class*="modal"] [class*="close"]').first.click(timeout=1000)
            page.wait_for_timeout(500)
        except Exception:
            pass

        try:
            close_buttons = page.locator(
                'button:has-text("关闭"), button:has-text("×")'
            ).all()
            for btn in close_buttons:
                try:
                    btn.click(timeout=500)
                except Exception:
                    pass
        except Exception:
            pass

        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    def _get_mooc_courses(self, page, timeout_ms: int) -> list[dict]:
        courses: list[dict] = []

        try:
            mooc_link = page.locator('a[href="#/home/course"]').first
            mooc_link.click()
            page.wait_for_timeout(3000)
        except Exception:
            pass

        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        page.wait_for_timeout(2000)

        html = page.content()

        learn_pattern = r"/learn/([A-Za-z]+-\d+)"
        course_keys = list(set(re.findall(learn_pattern, html)))

        for key in course_keys:
            try:
                course_url = f"https://www.icourse163.org/learn/{key}"
                page.goto(course_url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(3000)

                tid_match = re.search(r"tid=(\d+)", page.url)
                term_id = tid_match.group(1) if tid_match else ""

                if not term_id:
                    tid_match = re.search(r'termId[\s":]+(\d+)', page.content())
                    term_id = tid_match.group(1) if tid_match else ""

                title_match = re.search(r"<title>([^<]+)</title>", page.content())
                course_name = (
                    title_match.group(1)
                    .replace("_中国大学MOOC(慕课)", "")
                    .replace("_SPOC", "")
                    .strip()
                    if title_match
                    else key
                )

                courses.append(
                    {
                        "name": course_name,
                        "key": key,
                        "term_id": term_id,
                        "url": course_url,
                        "is_spoc": False,
                    }
                )
            except Exception:
                continue

        return courses

    def _get_spoc_courses(self, page, timeout_ms: int) -> list[dict]:
        courses: list[dict] = []

        page.goto(MOOC_HOME_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(3000)

        try:
            self._close_modals(page)
        except Exception:
            pass

        try:
            page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a[href="#/home/spocCourse"]');
                    if (links.length > 0) {
                        links[0].click();
                    }
                }
            """)
            page.wait_for_timeout(5000)
        except Exception:
            pass

        html = page.content()

        spoc_pattern = r"/spoc/learn/([A-Za-z]+-\d+)"
        course_keys = list(set(re.findall(spoc_pattern, html)))

        if not course_keys:
            spoc_pattern_alt = r"spoc/learn/([A-Za-z]+-\d+)"
            course_keys = list(set(re.findall(spoc_pattern_alt, html)))

        for key in course_keys:
            try:
                course_url = f"https://www.icourse163.org/spoc/learn/{key}"
                page.goto(course_url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(5000)

                title_match = re.search(r"<title>([^<]+)</title>", page.content())
                course_name = (
                    title_match.group(1)
                    .replace("_中国大学MOOC(慕课)", "")
                    .replace("_SPOC", "")
                    .strip()
                    if title_match
                    else key
                )

                courses.append(
                    {
                        "name": course_name,
                        "key": key,
                        "term_id": "",
                        "url": course_url,
                        "is_spoc": True,
                    }
                )
            except Exception:
                continue

        return courses

    def _crawl_single_course(
        self,
        page,
        course: dict,
        timeout_ms: int,
        now: datetime,
    ) -> list[CourseTask]:
        tasks: list[CourseTask] = []

        course_url = course["url"]
        page.goto(course_url, wait_until="domcontentloaded", timeout=timeout_ms)

        for wait_time in [3, 5, 8]:
            page.wait_for_timeout(wait_time * 1000)
            if "course" in page.url or "spoc" in page.url:
                break

        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(2000)

        is_spoc = course.get("is_spoc", False)

        if is_spoc:
            tasks.extend(self._get_spoc_work_items(page, course["name"]))
            tasks.extend(self._get_spoc_exam_items(page, course["name"]))
        else:
            tasks.extend(self._get_work_items(page, course["name"]))
            tasks.extend(self._get_exam_items(page, course["name"]))

        return tasks

    def _get_spoc_work_items(self, page, course_name: str) -> list[CourseTask]:
        items: list[CourseTask] = []

        try:
            page.wait_for_timeout(2000)

            hw_menu_selectors = [
                "li.ant-menu-item:has-text('测验与作业')",
                "li:has-text('测验与作业')",
                "[class*='ant-menu-item']:has-text('测验与作业')",
            ]

            clicked = False
            for selector in hw_menu_selectors:
                try:
                    count = page.locator(selector).count()
                    if count > 0:
                        tab = page.locator(selector).first
                        if tab.is_visible():
                            tab.click(timeout=3000)
                            clicked = True
                            page.wait_for_timeout(3000)
                            break
                except Exception:
                    pass

            if not clicked:
                page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('li.ant-menu-item, li[class*="menu"]');
                        for (const item of items) {
                            const text = item.innerText || '';
                            if (text.includes('测验与作业')) {
                                item.click();
                                break;
                            }
                        }
                    }
                """)
                page.wait_for_timeout(3000)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            hw_items = soup.select('.u-quizHwListItem, [class*="quizHwListItem"]')

            for hw_item in hw_items:
                title_el = hw_item.select_one(".j-name, .name, h4")
                deadline_el = hw_item.select_one('.j-submitTime, [class*="submitTime"]')

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                if len(title) < 5 or "作业" not in title:
                    continue

                deadline = ""
                if deadline_el:
                    deadline_text = deadline_el.get_text(strip=True)
                    dl_match = re.search(
                        r"(\d{4}[-/]\d{2}[-/]\d{2}\s*\d{1,2}:\d{2})", deadline_text
                    )
                    if dl_match:
                        deadline = dl_match.group(1).replace("/", "-")

                if deadline:
                    items.append(
                        CourseTask(
                            title=title[:100],
                            course_name=course_name,
                            deadline_text=deadline,
                            deadline_at=None,
                            url="",
                            source_platform="mooc",
                            task_type="assignment",
                        )
                    )

        except Exception:
            pass

        return items

    def _get_spoc_exam_items(self, page, course_name: str) -> list[CourseTask]:
        items: list[CourseTask] = []

        try:
            page.wait_for_timeout(2000)

            exam_menu_selectors = [
                "li.ant-menu-item:has-text('考试')",
                "li:has-text('考试')",
                "[class*='ant-menu-item']:has-text('考试')",
            ]

            clicked = False
            for selector in exam_menu_selectors:
                try:
                    count = page.locator(selector).count()
                    if count > 0:
                        tab = page.locator(selector).first
                        if tab.is_visible():
                            tab.click(timeout=3000)
                            clicked = True
                            page.wait_for_timeout(3000)
                            break
                except Exception:
                    pass

            if not clicked:
                page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('li.ant-menu-item, li[class*="menu"]');
                        for (const item of items) {
                            const text = item.innerText || '';
                            if (text.includes('考试') && !text.includes('测验')) {
                                item.click();
                                break;
                            }
                        }
                    }
                """)
                page.wait_for_timeout(3000)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            exam_items = soup.select(
                '.u-quizHwListItem, [class*="quizHwListItem"], [class*="examItem"]'
            )

            for exam_item in exam_items:
                title_el = exam_item.select_one(".j-name, .name, h4")
                deadline_el = exam_item.select_one(
                    '.j-submitTime, [class*="submitTime"]'
                )

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                if len(title) < 5 or "考试" not in title:
                    continue

                deadline = ""
                if deadline_el:
                    deadline_text = deadline_el.get_text(strip=True)
                    dl_match = re.search(
                        r"(\d{4}[-/]\d{2}[-/]\d{2}\s*\d{1,2}:\d{2})", deadline_text
                    )
                    if dl_match:
                        deadline = dl_match.group(1).replace("/", "-")

                if deadline:
                    items.append(
                        CourseTask(
                            title=title[:100],
                            course_name=course_name,
                            deadline_text=deadline,
                            deadline_at=None,
                            url="",
                            source_platform="mooc",
                            task_type="exam",
                        )
                    )

        except Exception:
            pass

        return items

    def _get_work_items(self, page, course_name: str) -> list[CourseTask]:
        items: list[CourseTask] = []

        try:
            page.wait_for_timeout(2000)

            work_tab_selectors = [
                "a:has-text('作业')",
                "li:has-text('作业')",
                "[data-type='work']",
                ".tab-item:has-text('作业')",
                "[class*='tab']:has-text('作业')",
                "div:has-text('作业')",
            ]

            clicked = False
            for selector in work_tab_selectors:
                try:
                    count = page.locator(selector).count()
                    if count > 0:
                        tab = page.locator(selector).first
                        if tab.is_visible():
                            tab.click(timeout=3000)
                            clicked = True
                            page.wait_for_timeout(3000)
                            break
                except Exception:
                    pass

            if not clicked:
                page.evaluate("""
                    () => {
                        const tabs = document.querySelectorAll('a, li, div, span');
                        for (const tab of tabs) {
                            if (tab.textContent.trim() === '作业') {
                                tab.click();
                                break;
                            }
                        }
                    }
                """)
                page.wait_for_timeout(3000)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            lists = soup.find_all(
                ["ul", "div"],
                class_=lambda x: (
                    x
                    and (
                        "list" in x.lower()
                        or "item" in x.lower()
                        or "work" in x.lower()
                    )
                ),
            )
            for list_elem in lists:
                for li in list_elem.find_all("li"):
                    task = self._parse_work_item(li, course_name)
                    if task:
                        items.append(task)

            if not items:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                text = soup.get_text()
                work_sections = re.findall(r"(.{0,30}作业.{0,100})", text)
                for section in work_sections[:5]:
                    deadline_match = re.search(
                        r"(\d{4}[-/]\d{2}[-/]\d{2}\s*\d{1,2}:\d{2})", section
                    )
                    if deadline_match:
                        title_match = re.search(r"([^\n截止]{2,30}?作业)", section)
                        if title_match:
                            items.append(
                                CourseTask(
                                    title=title_match.group(1).strip(),
                                    course_name=course_name,
                                    deadline_text=deadline_match.group(1).replace(
                                        "/", "-"
                                    ),
                                    deadline_at=None,
                                    url="",
                                    source_platform="mooc",
                                    task_type="assignment",
                                )
                            )

        except Exception:
            pass

        return items

    def _parse_work_item(self, element, course_name: str) -> CourseTask | None:
        try:
            text = element.get_text()
            if len(text) < 5:
                return None

            title = ""
            title_el = element.select_one("a, .title, .tit, [class*='tit']")
            if title_el:
                title = (
                    title_el.get("title", "") or title_el.get_text(strip=True)
                ).strip()

            if not title:
                return None

            deadline = ""
            dl_patterns = [
                r"截止[：:\s]*(\d{4}[-/]\d{2}[-/]\d{2}\s*\d{1,2}:\d{2})",
                r"(\d{4}[-/]\d{2}[-/]\d{2}\s*\d{1,2}:\d{2})",
            ]
            for pattern in dl_patterns:
                match = re.search(pattern, text)
                if match:
                    deadline = match.group(1).replace("/", "-")
                    break

            status = "unfinished"
            if any(kw in text for kw in ["已完成", "已提交", "已批改"]):
                status = "finished"
            elif "未开始" in text:
                status = "upcoming"

            if status == "finished":
                return None

            url = ""
            link = element.select_one("a[href]")
            if link:
                href = link.get("href", "")
                if (
                    href
                    and not href.startswith("#")
                    and not href.startswith("javascript")
                ):
                    url = (
                        href
                        if href.startswith("http")
                        else f"https://www.icourse163.org{href}"
                    )

            return CourseTask(
                title=title[:100],
                course_name=course_name,
                deadline_text=deadline,
                deadline_at=None,
                url=url,
                source_platform="mooc",
                task_type="assignment",
            )
        except Exception:
            return None

    def _get_exam_items(self, page, course_name: str) -> list[CourseTask]:
        items: list[CourseTask] = []

        try:
            page.wait_for_timeout(2000)

            exam_tab_selectors = [
                "a:has-text('考试')",
                "li:has-text('考试')",
                "[data-type='exam']",
                ".tab-item:has-text('考试')",
                "[class*='tab']:has-text('考试')",
                "div:has-text('考试')",
            ]

            clicked = False
            for selector in exam_tab_selectors:
                try:
                    count = page.locator(selector).count()
                    if count > 0:
                        tab = page.locator(selector).first
                        if tab.is_visible():
                            tab.click(timeout=3000)
                            clicked = True
                            page.wait_for_timeout(3000)
                            break
                except Exception:
                    pass

            if not clicked:
                page.evaluate("""
                    () => {
                        const tabs = document.querySelectorAll('a, li, div, span');
                        for (const tab of tabs) {
                            if (tab.textContent.trim() === '考试') {
                                tab.click();
                                break;
                            }
                        }
                    }
                """)
                page.wait_for_timeout(3000)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            text = soup.get_text()
            exam_sections = re.findall(r"(.{0,30}考试.{0,100})", text)
            for section in exam_sections[:5]:
                deadline_match = re.search(
                    r"(\d{4}[-/]\d{2}[-/]\d{2}\s*\d{1,2}:\d{2})", section
                )
                if deadline_match:
                    title_match = re.search(r"([^\n考试]{2,30}?考试)", section)
                    if title_match:
                        items.append(
                            CourseTask(
                                title=title_match.group(1).strip(),
                                course_name=course_name,
                                deadline_text=deadline_match.group(1).replace("/", "-"),
                                deadline_at=None,
                                url="",
                                source_platform="mooc",
                                task_type="exam",
                            )
                        )

        except Exception:
            pass

        return items
