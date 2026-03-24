from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup


@dataclass
class CourseTask:
    title: str
    course_name: str
    deadline_text: str
    deadline_at: datetime | None = None
    url: str = ""


def parse_pending_course_tasks(html: str) -> list[CourseTask]:
    soup = BeautifulSoup(html, "html.parser")
    tasks: list[CourseTask] = []

    for item in soup.select(".task-item"):
        course_name = item.select_one(".course-name")
        title = item.select_one(".task-title")
        deadline = item.select_one(".deadline")
        if not course_name or not title or not deadline:
            continue

        deadline_text = deadline.get_text(strip=True).removeprefix("截止时间：")
        tasks.append(
            CourseTask(
                title=title.get_text(strip=True),
                course_name=course_name.get_text(strip=True),
                deadline_text=deadline_text,
            )
        )

    return tasks
