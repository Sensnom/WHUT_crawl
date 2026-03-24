from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Callable

from config import Settings


@dataclass(frozen=True)
class HealthcheckCheck:
    name: str
    run: Callable[[], None]
    success_message: str
    failure_prefix: str
    handled_exceptions: tuple[type[BaseException], ...]


@dataclass(frozen=True)
class HealthcheckResult:
    name: str
    ok: bool
    message: str


def _check_output_dir_writable(output_dir: str) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path, prefix="healthcheck-", delete=True):
        pass


def _check_playwright_browser() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        executable_path = Path(playwright.chromium.executable_path)
        if not executable_path.exists():
            raise RuntimeError(
                f"Playwright Chromium executable not found: {executable_path}"
            )


def _build_healthcheck_checks(settings: Settings) -> list[HealthcheckCheck]:
    return [
        HealthcheckCheck(
            name="output directory",
            run=lambda: _check_output_dir_writable(settings.output_dir),
            success_message=f"output directory is writable: {settings.output_dir}",
            failure_prefix="output directory is not writable",
            handled_exceptions=(OSError,),
        ),
        HealthcheckCheck(
            name="Playwright browser",
            run=_check_playwright_browser,
            success_message="Playwright Chromium is available",
            failure_prefix="Playwright browser check failed",
            handled_exceptions=(ImportError, OSError, RuntimeError),
        ),
    ]


def _run_check(check: HealthcheckCheck) -> HealthcheckResult:
    try:
        check.run()
    except check.handled_exceptions as exc:
        return HealthcheckResult(
            name=check.name,
            ok=False,
            message=f"{check.failure_prefix}: {exc}",
        )
    return HealthcheckResult(name=check.name, ok=True, message=check.success_message)


def run_healthcheck(settings: Settings) -> int:
    print("[OK] settings loaded")
    results = [_run_check(check) for check in _build_healthcheck_checks(settings)]

    exit_code = 0
    for result in results:
        status = "OK" if result.ok else "ERROR"
        print(f"[{status}] {result.message}")
        if not result.ok:
            exit_code = 1

    return exit_code
