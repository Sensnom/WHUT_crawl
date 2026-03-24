from dataclasses import dataclass
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent


def parse_int_env(name: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"配置错误: {name} 必须是整数") from exc


def parse_bool_env(name: str, raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"配置错误: {name} 必须是布尔值")


def validate_settings(settings: "Settings") -> None:
    _validate_common_settings(settings)


def _validate_common_settings(
    settings: "Settings", *, require_api_key: bool = True
) -> None:
    errors: list[str] = []

    if require_api_key and not settings.api_key:
        errors.append("DEEPSEEK_API_KEY 不能为空")
    if settings.request_timeout <= 0:
        errors.append("REQUEST_TIMEOUT 必须是大于 0 的整数")
    if settings.max_pages <= 0:
        errors.append("MAX_PAGES 必须是大于 0 的整数")
    if not settings.output_dir:
        errors.append("OUTPUT_DIR 不能为空")
    if not 1 <= settings.smtp_port <= 65535:
        errors.append("SMTP_PORT 必须是 1-65535 的整数")
    if not 0 <= settings.schedule_hour <= 23:
        errors.append("SCHEDULE_HOUR 必须是 0-23 的整数")
    if not 0 <= settings.schedule_minute <= 59:
        errors.append("SCHEDULE_MINUTE 必须是 0-59 的整数")
    if not 0 <= settings.evening_schedule_hour <= 23:
        errors.append("EVENING_SCHEDULE_HOUR 必须是 0-23 的整数")
    if not 0 <= settings.evening_schedule_minute <= 59:
        errors.append("EVENING_SCHEDULE_MINUTE 必须是 0-59 的整数")
    if settings.backfill_max_days <= 0:
        errors.append("BACKFILL_MAX_DAYS 必须是大于 0 的整数")
    if settings.state_retention_days <= 0:
        errors.append("STATE_RETENTION_DAYS 必须是大于 0 的整数")

    try:
        ZoneInfo(settings.schedule_timezone)
    except ZoneInfoNotFoundError:
        errors.append("SCHEDULE_TIMEZONE 必须是有效时区")

    if errors:
        raise ValueError("配置错误: " + "; ".join(errors))


def _validate_email_settings(settings: "Settings") -> None:
    errors: list[str] = []

    if not settings.smtp_user:
        errors.append("SMTP_USER 不能为空")
    if not settings.smtp_app_password:
        errors.append("SMTP_APP_PASSWORD 不能为空")
    if not settings.email_to:
        errors.append("EMAIL_TO 不能为空")

    if errors:
        raise ValueError("配置错误: " + "; ".join(errors))


@dataclass
class Settings:
    api_key: str
    base_url: str
    model: str
    request_timeout: int
    list_url: str = "http://i.whut.edu.cn/xxtg/"
    output_dir: str = str(PROJECT_ROOT / "output")
    target_source: str = "本科生院"
    max_pages: int = 3
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_app_password: str = ""
    email_to: str = ""
    course_page_url: str = "https://whut.ai-augmented.com/app/jx-web/mycourse"
    smart_whut_username: str = ""
    smart_whut_password: str = ""
    schedule_timezone: str = "Asia/Shanghai"
    schedule_hour: int = 12
    schedule_minute: int = 0
    evening_schedule_hour: int = 18
    evening_schedule_minute: int = 0
    backfill_max_days: int = 7
    state_retention_days: int = 15
    enable_news_service: bool = True
    enable_course_service: bool = True

    @classmethod
    def from_env(cls, *, validate: bool = True) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        settings = cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip(),
            request_timeout=parse_int_env(
                "REQUEST_TIMEOUT", os.getenv("REQUEST_TIMEOUT", "60")
            ),
            output_dir=os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "output")).strip(),
            target_source=os.getenv("TARGET_SOURCE", "本科生院").strip(),
            max_pages=parse_int_env("MAX_PAGES", os.getenv("MAX_PAGES", "3")),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
            smtp_port=parse_int_env("SMTP_PORT", os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", "").strip(),
            smtp_app_password=os.getenv("SMTP_APP_PASSWORD", "").strip(),
            email_to=os.getenv("EMAIL_TO", "").strip(),
            course_page_url=os.getenv(
                "COURSE_PAGE_URL",
                "https://whut.ai-augmented.com/app/jx-web/mycourse",
            ).strip(),
            smart_whut_username=os.getenv("SMART_WHUT_USERNAME", "").strip(),
            smart_whut_password=os.getenv("SMART_WHUT_PASSWORD", "").strip(),
            schedule_timezone=os.getenv("SCHEDULE_TIMEZONE", "Asia/Shanghai").strip(),
            schedule_hour=parse_int_env(
                "SCHEDULE_HOUR", os.getenv("SCHEDULE_HOUR", "12")
            ),
            schedule_minute=parse_int_env(
                "SCHEDULE_MINUTE", os.getenv("SCHEDULE_MINUTE", "0")
            ),
            evening_schedule_hour=parse_int_env(
                "EVENING_SCHEDULE_HOUR", os.getenv("EVENING_SCHEDULE_HOUR", "18")
            ),
            evening_schedule_minute=parse_int_env(
                "EVENING_SCHEDULE_MINUTE", os.getenv("EVENING_SCHEDULE_MINUTE", "0")
            ),
            backfill_max_days=parse_int_env(
                "BACKFILL_MAX_DAYS", os.getenv("BACKFILL_MAX_DAYS", "7")
            ),
            state_retention_days=parse_int_env(
                "STATE_RETENTION_DAYS", os.getenv("STATE_RETENTION_DAYS", "15")
            ),
            enable_news_service=parse_bool_env(
                "ENABLE_NEWS_SERVICE", os.getenv("ENABLE_NEWS_SERVICE", "true")
            ),
            enable_course_service=parse_bool_env(
                "ENABLE_COURSE_SERVICE", os.getenv("ENABLE_COURSE_SERVICE", "true")
            ),
        )
        if validate:
            validate_settings(settings)
        return settings

    @staticmethod
    def validate_for_mode(settings: "Settings", mode: str) -> None:
        _validate_common_settings(settings, require_api_key=mode != "healthcheck")

        if mode in {"run", "news"}:
            _validate_email_settings(settings)
            return
        if mode == "healthcheck":
            return

        raise ValueError(f"不支持的运行模式: {mode}")
