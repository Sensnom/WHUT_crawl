from config import Settings
import pytest


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("TARGET_SOURCE", "本科生院")
    monkeypatch.setenv("MAX_PAGES", "4")
    settings = Settings.from_env()
    assert settings.api_key == "test-key"
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.model == "deepseek-chat"
    assert settings.request_timeout == 30
    assert settings.target_source == "本科生院"
    assert settings.max_pages == 4


def test_settings_reads_smtp_fields(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app-pass")
    monkeypatch.setenv("EMAIL_TO", "receiver@example.com")
    settings = Settings.from_env()
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 587
    assert settings.smtp_user == "user@example.com"
    assert settings.smtp_app_password == "app-pass"
    assert settings.email_to == "receiver@example.com"


def test_settings_reads_course_site_credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv(
        "COURSE_PAGE_URL", "https://whut.ai-augmented.com/app/jx-web/mycourse"
    )
    monkeypatch.setenv("SMART_WHUT_USERNAME", "2020123456")
    monkeypatch.setenv("SMART_WHUT_PASSWORD", "secret")

    settings = Settings.from_env()

    assert (
        settings.course_page_url == "https://whut.ai-augmented.com/app/jx-web/mycourse"
    )
    assert settings.smart_whut_username == "2020123456"
    assert settings.smart_whut_password == "secret"


def test_settings_reads_evening_and_retention_fields(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("EVENING_SCHEDULE_HOUR", "18")
    monkeypatch.setenv("EVENING_SCHEDULE_MINUTE", "0")
    monkeypatch.setenv("BACKFILL_MAX_DAYS", "7")
    monkeypatch.setenv("STATE_RETENTION_DAYS", "15")
    settings = Settings.from_env()
    assert settings.evening_schedule_hour == 18
    assert settings.evening_schedule_minute == 0
    assert settings.backfill_max_days == 7
    assert settings.state_retention_days == 15


def test_settings_enable_both_services_by_default(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    settings = Settings.from_env()

    assert settings.enable_news_service is True
    assert settings.enable_course_service is True


def test_settings_reads_disabled_news_service_toggle(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_NEWS_SERVICE", "false")

    settings = Settings.from_env()

    assert settings.enable_news_service is False
    assert settings.enable_course_service is True


def test_settings_reads_disabled_course_service_toggle(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_COURSE_SERVICE", "0")

    settings = Settings.from_env()

    assert settings.enable_news_service is True
    assert settings.enable_course_service is False


def test_settings_rejects_invalid_service_toggle(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_NEWS_SERVICE", "maybe")

    with pytest.raises(ValueError, match="ENABLE_NEWS_SERVICE"):
        Settings.from_env()


def test_settings_uses_noon_schedule_by_default(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("SCHEDULE_HOUR", raising=False)

    settings = Settings.from_env()

    assert settings.schedule_hour == 12


def test_settings_loads_dotenv_from_project_root(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env").write_text(
        "DEEPSEEK_API_KEY=from-file\n",
        encoding="utf-8",
    )
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    monkeypatch.chdir(outside_dir)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("config.PROJECT_ROOT", project_root)

    settings = Settings.from_env()

    assert settings.api_key == "from-file"
    assert settings.output_dir == str(project_root / "output")


def test_settings_rejects_invalid_schedule_hour(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("SCHEDULE_HOUR", "24")

    with pytest.raises(ValueError, match="SCHEDULE_HOUR"):
        Settings.from_env()


def test_settings_rejects_non_integer_numeric_field(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("REQUEST_TIMEOUT", "abc")

    with pytest.raises(ValueError, match="REQUEST_TIMEOUT"):
        Settings.from_env()


def test_settings_rejects_invalid_timezone(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("SCHEDULE_TIMEZONE", "Asia/Shangha")

    with pytest.raises(ValueError, match="SCHEDULE_TIMEZONE"):
        Settings.from_env()


def test_settings_rejects_non_positive_max_pages(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("MAX_PAGES", "0")

    with pytest.raises(ValueError, match="MAX_PAGES"):
        Settings.from_env()


def test_settings_rejects_invalid_smtp_port(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("SMTP_PORT", "70000")

    with pytest.raises(ValueError, match="SMTP_PORT"):
        Settings.from_env()


def test_settings_rejects_blank_output_dir(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("OUTPUT_DIR", "   ")

    with pytest.raises(ValueError, match="OUTPUT_DIR"):
        Settings.from_env()


def test_settings_can_validate_healthcheck_without_mail_credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_APP_PASSWORD", raising=False)
    monkeypatch.delenv("EMAIL_TO", raising=False)

    settings = Settings.from_env()

    Settings.validate_for_mode(settings, "healthcheck")


def test_settings_reads_chaoxing_fields(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("CHAOXING_USERNAME", "13800000000")
    monkeypatch.setenv("CHAOXING_PASSWORD", "secret")
    monkeypatch.setenv("CHAOXING_TARGET_COURSE_NAMES", "高数, 大学物理 ")
    monkeypatch.setenv("ENABLE_CHAOXING_SERVICE", "true")

    settings = Settings.from_env()

    assert settings.chaoxing_username == "13800000000"
    assert settings.chaoxing_password == "secret"
    assert settings.chaoxing_target_course_names == ["高数", "大学物理"]
    assert settings.enable_chaoxing_service is True
