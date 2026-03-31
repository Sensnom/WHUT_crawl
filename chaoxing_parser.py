from datetime import datetime

from bs4 import BeautifulSoup

from course_parser import CourseTask


def parse_deadline(raw: str, now: datetime) -> tuple[str, datetime | None]:
    text = raw.strip()
    if not text:
        return "", None
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%Y-%m-%d %H:%M"), dt
    except ValueError:
        pass
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%d %H:%M"), dt
    except ValueError:
        pass
    return text, None


def _course_matches(course_name: str, target_names: list[str]) -> bool:
    if not target_names:
        return True
    cn = course_name.strip()
    return any(cn == tn.strip() or cn.startswith(tn.strip()) for tn in target_names)


def parse_chaoxing_assignment_page(
    html: str, target_course_names: list[str], now: datetime
) -> list[CourseTask]:
    soup = BeautifulSoup(html, "html.parser")
    tasks: list[CourseTask] = []

    for row in soup.select(".grid_item, .assignment-item, .homework-item, li"):
        course_el = row.select_one(".course-name, .courseTitle, [class*=course]")
        title_el = row.select_one(".title, .task-title, .homeworkTitle, a")
        status_el = row.select_one(".status, .state")
        deadline_el = row.select_one(".deadline, .endTime, .time")

        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        course_name = course_el.get_text(strip=True) if course_el else ""
        status = status_el.get_text(strip=True).lower() if status_el else ""

        if (
            "已完成" in status
            or "已提交" in status
            or "done" in status
            or "submitted" in status
        ):
            continue

        deadline_raw = deadline_el.get_text(strip=True) if deadline_el else ""
        deadline_text, deadline_at = parse_deadline(deadline_raw, now)

        if deadline_at is None:
            continue
        if deadline_at < now or (deadline_at - now).days > 30:
            continue
        if not _course_matches(course_name, target_course_names):
            continue

        tasks.append(
            CourseTask(
                title=title,
                course_name=course_name,
                deadline_text=deadline_text,
                deadline_at=deadline_at,
                source_platform="chaoxing",
                task_type="assignment",
            )
        )

    return tasks


def parse_chaoxing_exam_page(
    html: str, target_course_names: list[str], now: datetime
) -> list[CourseTask]:
    soup = BeautifulSoup(html, "html.parser")
    tasks: list[CourseTask] = []

    for row in soup.select(".grid_item, .exam-item, .test-item, li"):
        course_el = row.select_one(".course-name, .courseTitle")
        title_el = row.select_one(".title, .examTitle, .testTitle, a")
        status_el = row.select_one(".status, .state")
        deadline_el = row.select_one(".deadline, .endTime, .time")

        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        course_name = course_el.get_text(strip=True) if course_el else ""
        status = status_el.get_text(strip=True).lower() if status_el else ""

        if (
            "已完成" in status
            or "已交" in status
            or "已结束" in status
            or "已考" in status
            or "done" in status
            or "submitted" in status
        ) and "未" not in status:
            continue

        deadline_raw = deadline_el.get_text(strip=True) if deadline_el else ""
        deadline_text, deadline_at = parse_deadline(deadline_raw, now)

        if deadline_at is None:
            continue
        if deadline_at < now or (deadline_at - now).days > 30:
            continue
        if not _course_matches(course_name, target_course_names):
            continue

        tasks.append(
            CourseTask(
                title=title,
                course_name=course_name,
                deadline_text=deadline_text,
                deadline_at=deadline_at,
                source_platform="chaoxing",
                task_type="exam",
            )
        )

    return tasks


def parse_chaoxing_items(
    raw_items: list[dict],
    now: datetime,
    target_course_names: list[str],
) -> list[CourseTask]:
    tasks: list[CourseTask] = []

    for item in raw_items:
        course_name = str(item.get("course_name", "")).strip()
        title = str(item.get("title", "")).strip()
        status = str(item.get("status", "")).lower()
        task_type = str(item.get("task_type", "assignment")).lower()
        deadline_raw = str(item.get("deadline", "")).strip()

        if not title:
            continue
        if (
            ("完成" in status and "未" not in status)
            or "已交" in status
            or "已结束" in status
            or "已考" in status
            or "done" in status
            or "submitted" in status
        ):
            continue
        if not _course_matches(course_name, target_course_names):
            continue

        deadline_text, deadline_at = parse_deadline(deadline_raw, now)

        if deadline_at is None:
            continue
        if deadline_at < now or (deadline_at - now).days > 30:
            continue

        tasks.append(
            CourseTask(
                title=title,
                course_name=course_name,
                deadline_text=deadline_text,
                deadline_at=deadline_at,
                source_platform="chaoxing",
                task_type=task_type
                if task_type in ("assignment", "exam")
                else "assignment",
            )
        )

    return tasks
