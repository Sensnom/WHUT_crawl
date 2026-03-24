import argparse
import grp
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT_DIR = CURRENT_FILE.parent.parent
if str(PROJECT_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_DIR))

from config import PROJECT_ROOT, Settings


SCHEDULER_DIR = Path(__file__).resolve().parent
SERVICE_TEMPLATE_PATH = SCHEDULER_DIR / "network-crawl.service"
TIMER_TEMPLATE_PATH = SCHEDULER_DIR / "network-crawl.timer"
SERVICE_OUTPUT_NAME = "network-crawl.service"
TIMER_OUTPUT_NAME = "network-crawl.timer"
SYSTEMD_UNIT_DIR = Path("/etc/systemd/system")
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "systemd"


def load_template(template_path: Path) -> str:
    return template_path.read_text(encoding="utf-8")


def replace_placeholders(template_text: str, replacements: dict[str, str]) -> str:
    rendered = template_text
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def render_service_template(
    *,
    project_root: str,
    python_bin: str,
    service_user: str,
    service_group: str,
) -> str:
    return replace_placeholders(
        load_template(SERVICE_TEMPLATE_PATH),
        {
            "<PROJECT_ROOT>": project_root,
            "<PYTHON_BIN>": python_bin,
            "<SERVICE_USER>": service_user,
            "<SERVICE_GROUP>": service_group,
        },
    )


def render_timer_template(*, schedule_timezone: str) -> str:
    return replace_placeholders(
        load_template(TIMER_TEMPLATE_PATH),
        {"<SCHEDULE_TIMEZONE>": schedule_timezone},
    )


def write_rendered_units(
    *, output_dir: Path, service_text: str, timer_text: str
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    service_path = output_dir / SERVICE_OUTPUT_NAME
    timer_path = output_dir / TIMER_OUTPUT_NAME
    service_path.write_text(service_text, encoding="utf-8")
    timer_path.write_text(timer_text, encoding="utf-8")
    return {"service": service_path, "timer": timer_path}


def install_rendered_units(
    *, rendered_service_path: Path, rendered_timer_path: Path
) -> None:
    if os.geteuid() != 0:
        raise PermissionError("Install mode requires root privileges. Please use sudo.")

    shutil.copy2(rendered_service_path, SYSTEMD_UNIT_DIR / SERVICE_OUTPUT_NAME)
    shutil.copy2(rendered_timer_path, SYSTEMD_UNIT_DIR / TIMER_OUTPUT_NAME)

    try:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("systemctl daemon-reload failed") from error

    try:
        subprocess.run(
            ["systemctl", "enable", "--now", TIMER_OUTPUT_NAME],
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"systemctl enable --now {TIMER_OUTPUT_NAME} failed"
        ) from error


def uninstall_systemd_units() -> None:
    if os.geteuid() != 0:
        raise PermissionError(
            "Uninstall mode requires root privileges. Please use sudo."
        )

    try:
        subprocess.run(["systemctl", "disable", "--now", TIMER_OUTPUT_NAME], check=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"systemctl disable --now {TIMER_OUTPUT_NAME} failed"
        ) from error

    (SYSTEMD_UNIT_DIR / TIMER_OUTPUT_NAME).unlink(missing_ok=True)
    (SYSTEMD_UNIT_DIR / SERVICE_OUTPUT_NAME).unlink(missing_ok=True)

    try:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("systemctl daemon-reload failed") from error


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render, install, or uninstall systemd units."
    )
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--render", action="store_true", help="Write rendered units."
    )
    action_group.add_argument(
        "--install", action="store_true", help="Install rendered units into systemd."
    )
    action_group.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove installed units from systemd.",
    )
    return parser.parse_args(argv)


def get_service_identity() -> tuple[str, str]:
    sudo_user = os.getenv("SUDO_USER", "").strip()
    if os.geteuid() == 0 and sudo_user:
        user = pwd.getpwnam(sudo_user)
    else:
        user = pwd.getpwuid(os.getuid())
    group = grp.getgrgid(user.pw_gid)
    return user.pw_name, group.gr_name


def build_rendered_units(settings: Settings) -> dict[str, str]:
    service_user, service_group = get_service_identity()
    return {
        "service": render_service_template(
            project_root=str(PROJECT_ROOT),
            python_bin=sys.executable,
            service_user=service_user,
            service_group=service_group,
        ),
        "timer": render_timer_template(
            schedule_timezone=settings.schedule_timezone,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.uninstall:
        uninstall_systemd_units()
        return 0

    settings = Settings.from_env()
    rendered_units = build_rendered_units(settings)
    written_paths = write_rendered_units(
        output_dir=DEFAULT_OUTPUT_DIR,
        service_text=rendered_units["service"],
        timer_text=rendered_units["timer"],
    )

    if args.install:
        install_rendered_units(
            rendered_service_path=written_paths["service"],
            rendered_timer_path=written_paths["timer"],
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
