import os
from pathlib import Path

import pytest

from config import Settings


def test_smoke_env_present_or_skip():
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set; skipping live smoke test")
    settings = Settings.from_env()
    assert settings.api_key


def test_readme_documents_gmail_env_fields():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "SMTP_HOST" in readme
    assert "SMTP_APP_PASSWORD" in readme
    assert "EMAIL_TO" in readme
    assert "18:00" in readme
    assert "补发" in readme
    assert "SCHEDULE_TIMEZONE" in readme
    assert "SCHEDULE_HOUR=12" in readme
    assert "STATE_RETENTION_DAYS=15" in readme


def test_readme_does_not_hardcode_local_absolute_paths():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert '"<PYTHON_BIN>" "<PROJECT_ROOT>/main.py"' in readme
    assert "WorkingDirectory=<PROJECT_ROOT>" in readme


def test_readme_documents_uv_workflow():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "uv sync" in readme
    assert "uv run python main.py" in readme
    assert "uv run pytest -v" in readme


def test_readme_documents_course_task_email_setup():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "SMART_WHUT_USERNAME" in readme
    assert "课程任务邮件" in readme


def test_readme_documents_playwright_install_for_course_tasks():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "uv add playwright" in readme or "playwright install" in readme


def test_readme_mentions_systemd_as_primary_linux_scheduler():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Linux 部署统一使用 `systemd`" in readme
    assert "scheduler/network-crawl.service" in readme
    assert "scheduler/network-crawl.timer" in readme
    assert "scheduler/manage_systemd.py" in readme
    assert "output/systemd/" in readme
    assert "安装到 `/etc/systemd/system/`" in readme
    assert "sudo uv run python scheduler/manage_systemd.py --install" in readme
    assert "`Persistent=true`" in readme
    assert "`Timezone=`" in readme
    assert "和 `.env` 里的 `SCHEDULE_TIMEZONE` 保持一致" in readme
    assert "错过的触发会在机器恢复后尽快补跑一次" in readme


def test_readme_no_longer_mentions_cron_fallback():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "scheduler/manage_cron.py" not in readme
    assert "scheduler/cron.example" not in readme
    assert "### 4.2 cron" not in readme
    assert "cron.log" not in readme


def test_readme_documents_manage_systemd_commands():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "manage_systemd.py --render" in readme
    assert "manage_systemd.py --install" in readme
    assert "manage_systemd.py --uninstall" in readme
