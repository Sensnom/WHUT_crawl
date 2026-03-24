import json

import requests

from config import Settings
from models import NoticeItem


def build_prompt(notices: list[NoticeItem], max_chars_per_notice: int = 1600) -> str:
    lines = [
        "请把以下武汉理工大学通知总结为中文简明要点（3-8条）。",
        "每条尽量包含：事项、涉及对象、时间节点/要求（若有）。",
        "不要写无关前言。",
        "",
    ]
    for idx, item in enumerate(notices, 1):
        content = item.content[:max_chars_per_notice]
        lines.extend(
            [
                f"[{idx}] 标题: {item.title}",
                f"发布时间: {item.publish_time:%Y-%m-%d %H:%M}",
                f"发布单位: {item.source or '未知'}",
                f"链接: {item.url}",
                f"正文:\n{content}",
                "",
            ]
        )
    return "\n".join(lines)


def summarize_with_deepseek(
    notices: list[NoticeItem], settings: Settings, retries: int = 1
) -> str:
    if not notices:
        return "最近三天没有可总结的通知。"

    prompt = build_prompt(notices)
    endpoint = settings.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": "你是高校通知助手，输出清晰、简洁、准确。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }

    last_error = None
    for _ in range(retries + 1):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=settings.request_timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content:
                return content
        except Exception as exc:
            last_error = exc

    return fallback_summary(notices, str(last_error) if last_error else "unknown error")


def fallback_summary(notices: list[NoticeItem], reason: str) -> str:
    lines = ["DeepSeek 总结失败，输出原始通知简表：", f"失败原因: {reason}", ""]
    for item in notices:
        lines.append(f"- {item.publish_time:%Y-%m-%d} | {item.title} | {item.url}")
    return "\n".join(lines)
