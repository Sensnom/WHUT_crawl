from datetime import datetime

from config import Settings
from models import NoticeItem
from summarizer import build_prompt, summarize_with_deepseek


def test_build_prompt_contains_notice_fields():
    notices = [
        NoticeItem(
            title="标题",
            url="http://example.com/1",
            publish_time=datetime(2026, 3, 18, 9, 0),
            source="本科生院",
            content="正文内容",
        )
    ]
    prompt = build_prompt(notices)
    assert "标题" in prompt
    assert "2026-03-18 09:00" in prompt
    assert "正文内容" in prompt


def test_summarize_with_deepseek_fallback_on_error(monkeypatch):
    def fake_post(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("summarizer.requests.post", fake_post)

    settings = Settings(
        api_key="k",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        request_timeout=10,
    )
    notices = [
        NoticeItem(
            title="标题",
            url="http://example.com/1",
            publish_time=datetime(2026, 3, 18, 9, 0),
            content="正文内容",
        )
    ]
    result = summarize_with_deepseek(notices, settings)
    assert "原始通知简表" in result
