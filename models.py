from dataclasses import dataclass
from datetime import datetime


@dataclass
class NoticeItem:
    title: str
    url: str
    publish_time: datetime
    source: str = ""
    content: str = ""
