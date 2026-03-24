from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from models import NoticeItem


def parse_date(value: str) -> datetime | None:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_list_page(html: str, base_url: str) -> list[NoticeItem]:
    soup = BeautifulSoup(html, "html.parser")
    notices: list[NoticeItem] = []

    date_pattern = r"\d{4}[-/]\d{2}[-/]\d{2}(?:\s+\d{2}:\d{2})?"
    for li in soup.select("li"):
        text = li.get_text(" ", strip=True)
        date_match = re.search(date_pattern, text)
        if not date_match:
            continue

        publish_time = parse_date(date_match.group(0))
        if publish_time is None:
            continue

        links = [link for link in li.find_all("a") if isinstance(link, Tag)]
        if not links:
            continue

        notice_link = links[-1]
        href_value = notice_link.get("href")
        title_value = notice_link.get("title")
        href = href_value.strip() if isinstance(href_value, str) else ""
        title = (
            title_value
            if isinstance(title_value, str)
            else notice_link.get_text(strip=True)
        )
        if not href or not title:
            continue

        source = ""
        if len(links) >= 2:
            source = links[0].get_text(strip=True).strip("【】")

        notices.append(
            NoticeItem(
                title=title,
                url=urljoin(base_url, href),
                publish_time=publish_time,
                source=source,
            )
        )

    return notices


def filter_recent_notices(
    notices: list[NoticeItem], now: datetime, hours: int = 72
) -> list[NoticeItem]:
    threshold = now - timedelta(hours=hours)
    return [item for item in notices if item.publish_time >= threshold]


def filter_source_notices(
    notices: list[NoticeItem], target_source: str
) -> list[NoticeItem]:
    target = target_source.strip()
    if not target:
        return notices
    return [item for item in notices if item.source == target]
