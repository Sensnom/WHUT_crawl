from pathlib import Path

from config import Settings
from app.healthcheck import run_healthcheck


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        request_timeout=30,
        output_dir=str(tmp_path),
        target_source="本科生院",
    )


def test_run_healthcheck_succeeds_with_settings_only(monkeypatch, tmp_path, capsys):
    settings = make_settings(tmp_path)
    checks: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "app.healthcheck._check_output_dir_writable",
        lambda output_dir: checks.append(("output", output_dir)),
    )
    monkeypatch.setattr(
        "app.healthcheck._check_playwright_browser",
        lambda: checks.append(("browser", "ok")),
    )

    assert run_healthcheck(settings) == 0
    assert checks == [("output", settings.output_dir), ("browser", "ok")]
    assert "[OK] settings loaded" in capsys.readouterr().out


def test_run_healthcheck_reports_browser_failure(monkeypatch, tmp_path, capsys):
    settings = make_settings(tmp_path)

    monkeypatch.setattr(
        "app.healthcheck._check_output_dir_writable", lambda _output_dir: None
    )
    monkeypatch.setattr(
        "app.healthcheck._check_playwright_browser",
        lambda: (_ for _ in ()).throw(RuntimeError("browser missing")),
    )

    assert run_healthcheck(settings) == 1
    assert "browser missing" in capsys.readouterr().out


def test_run_healthcheck_reports_multiple_named_checks(monkeypatch, tmp_path, capsys):
    settings = make_settings(tmp_path)

    monkeypatch.setattr(
        "app.healthcheck._check_output_dir_writable",
        lambda _output_dir: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr("app.healthcheck._check_playwright_browser", lambda: None)

    assert run_healthcheck(settings) == 1

    output = capsys.readouterr().out
    assert "[ERROR] output directory" in output
    assert "disk full" in output
    assert "[OK] Playwright Chromium is available" in output
