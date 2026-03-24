from pathlib import Path
import subprocess

import pytest


def _parse_systemd_unit(path: str) -> dict[str, dict[str, list[str]]]:
    sections: dict[str, dict[str, list[str]]] = {}
    current_section: str | None = None

    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            sections[current_section] = {}
            continue

        if current_section is None:
            raise ValueError(
                f"Unit entry appears before any section header: {raw_line}"
            )

        key, value = line.split("=", maxsplit=1)
        sections[current_section].setdefault(key, []).append(value)

    return sections


def test_scheduler_directory_no_longer_contains_cron_compatibility_files():
    assert not Path("scheduler/manage_cron.py").exists()
    assert not Path("scheduler/cron.example").exists()


def test_systemd_service_template_preserves_project_root_and_space_safe_exec_args():
    sections = _parse_systemd_unit("scheduler/network-crawl.service")

    assert set(sections) == {"Unit", "Service"}
    assert sections["Service"]["Type"] == ["oneshot"]
    assert sections["Service"]["User"] == ["<SERVICE_USER>"]
    assert sections["Service"]["Group"] == ["<SERVICE_GROUP>"]
    assert sections["Service"]["WorkingDirectory"] == ["<PROJECT_ROOT>"]
    assert sections["Service"]["ExecStartPre"] == [
        '/usr/bin/mkdir -p "<PROJECT_ROOT>/output"'
    ]
    assert sections["Service"]["ExecStart"] == [
        '"<PYTHON_BIN>" "<PROJECT_ROOT>/main.py"'
    ]


def test_systemd_service_template_includes_placeholder_guidance_for_manual_edits():
    content = Path("scheduler/network-crawl.service").read_text(encoding="utf-8")

    assert "Replace <PROJECT_ROOT> and <PYTHON_BIN> with absolute paths." in content
    assert (
        "Replace <SERVICE_USER> and <SERVICE_GROUP> with the non-root account"
        in content
    )
    assert (
        "Keep the ExecStart arguments quoted if either path contains spaces." in content
    )


def test_systemd_timer_schedules_noon_and_evening_runs_and_is_installable_unit():
    sections = _parse_systemd_unit("scheduler/network-crawl.timer")

    assert set(sections) == {"Unit", "Timer", "Install"}
    assert sections["Timer"]["Timezone"] == ["<SCHEDULE_TIMEZONE>"]
    assert sections["Timer"]["OnCalendar"] == ["*-*-* 12:00:00", "*-*-* 18:00:00"]
    assert sections["Timer"]["Persistent"] == ["true"]
    assert sections["Timer"]["Unit"] == ["network-crawl.service"]
    assert sections["Install"]["WantedBy"] == ["timers.target"]


def test_systemd_timer_template_includes_timezone_alignment_guidance():
    content = Path("scheduler/network-crawl.timer").read_text(encoding="utf-8")

    assert (
        "Replace <SCHEDULE_TIMEZONE> with the same value as .env SCHEDULE_TIMEZONE."
        in content
    )


def test_rendered_service_file_replaces_template_placeholders(tmp_path):
    from scheduler.manage_systemd import render_service_template

    rendered = render_service_template(
        project_root="/srv/network-crawl",
        python_bin="/srv/network-crawl/.venv/bin/python",
        service_user="crawler",
        service_group="crawler",
    )

    assert "<PROJECT_ROOT>" not in rendered
    assert "<PYTHON_BIN>" not in rendered
    assert "<SERVICE_USER>" not in rendered
    assert "<SERVICE_GROUP>" not in rendered
    assert "WorkingDirectory=/srv/network-crawl" in rendered
    assert (
        'ExecStart="/srv/network-crawl/.venv/bin/python" '
        '"/srv/network-crawl/main.py"' in rendered
    )


def test_render_command_writes_units_to_output_directory(tmp_path):
    from scheduler.manage_systemd import write_rendered_units

    paths = write_rendered_units(
        output_dir=tmp_path,
        service_text="[Service]\nWorkingDirectory=/srv/app\n",
        timer_text="[Timer]\nTimezone=Asia/Shanghai\n",
    )

    assert paths["service"].read_text(encoding="utf-8").startswith("[Service]")
    assert paths["timer"].read_text(encoding="utf-8").startswith("[Timer]")


def test_install_mode_requires_root(monkeypatch, tmp_path):
    from scheduler.manage_systemd import install_rendered_units

    monkeypatch.setattr("os.geteuid", lambda: 1000)

    with pytest.raises(PermissionError, match="sudo"):
        install_rendered_units(
            rendered_service_path=tmp_path / "network-crawl.service",
            rendered_timer_path=tmp_path / "network-crawl.timer",
        )


def test_install_mode_copies_units_and_runs_systemctl_in_order(monkeypatch, tmp_path):
    from scheduler.manage_systemd import install_rendered_units

    service_path = tmp_path / "network-crawl.service"
    timer_path = tmp_path / "network-crawl.timer"
    service_path.write_text("[Service]\n", encoding="utf-8")
    timer_path.write_text("[Timer]\n", encoding="utf-8")

    calls: list[tuple[str, object]] = []

    monkeypatch.setattr("os.geteuid", lambda: 0)

    def fake_copy2(src, dst):
        calls.append(("copy2", (Path(src), Path(dst))))

    def fake_run(command, check):
        calls.append(("run", (command, check)))

    monkeypatch.setattr("shutil.copy2", fake_copy2)
    monkeypatch.setattr("subprocess.run", fake_run)

    install_rendered_units(
        rendered_service_path=service_path,
        rendered_timer_path=timer_path,
    )

    assert calls == [
        (
            "copy2",
            (service_path, Path("/etc/systemd/system/network-crawl.service")),
        ),
        (
            "copy2",
            (timer_path, Path("/etc/systemd/system/network-crawl.timer")),
        ),
        ("run", (["systemctl", "daemon-reload"], True)),
        (
            "run",
            (["systemctl", "enable", "--now", "network-crawl.timer"], True),
        ),
    ]


def test_manage_systemd_parse_args_supports_render_and_install():
    from scheduler.manage_systemd import parse_args

    args = parse_args(["--render"])

    assert args.render is True
    assert args.install is False
    assert args.uninstall is False


def test_manage_systemd_parse_args_supports_uninstall():
    from scheduler.manage_systemd import parse_args

    args = parse_args(["--uninstall"])

    assert args.render is False
    assert args.install is False
    assert args.uninstall is True


def test_manage_systemd_parse_args_requires_an_action():
    from scheduler.manage_systemd import parse_args

    with pytest.raises(SystemExit, match="2"):
        parse_args([])


def test_get_service_identity_prefers_sudo_user_when_running_as_root(monkeypatch):
    from scheduler.manage_systemd import get_service_identity

    monkeypatch.setattr("os.geteuid", lambda: 0)
    monkeypatch.setenv("SUDO_USER", "crawler")

    class FakeUser:
        pw_name = "crawler"
        pw_gid = 1234

    class FakeGroup:
        gr_name = "crawler"

    monkeypatch.setattr("pwd.getpwnam", lambda username: FakeUser())
    monkeypatch.setattr("grp.getgrgid", lambda gid: FakeGroup())

    service_user, service_group = get_service_identity()

    assert service_user == "crawler"
    assert service_group == "crawler"


def test_install_mode_wraps_systemctl_failures_with_readable_message(
    monkeypatch, tmp_path
):
    from scheduler.manage_systemd import install_rendered_units

    service_path = tmp_path / "network-crawl.service"
    timer_path = tmp_path / "network-crawl.timer"
    service_path.write_text("[Service]\n", encoding="utf-8")
    timer_path.write_text("[Timer]\n", encoding="utf-8")

    monkeypatch.setattr("os.geteuid", lambda: 0)
    monkeypatch.setattr("shutil.copy2", lambda src, dst: None)

    def fake_run(command, check):
        raise subprocess.CalledProcessError(returncode=1, cmd=command)

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="systemctl daemon-reload failed"):
        install_rendered_units(
            rendered_service_path=service_path,
            rendered_timer_path=timer_path,
        )


def test_uninstall_mode_requires_root(monkeypatch):
    from scheduler.manage_systemd import uninstall_systemd_units

    monkeypatch.setattr("os.geteuid", lambda: 1000)

    with pytest.raises(PermissionError, match="sudo"):
        uninstall_systemd_units()


def test_uninstall_mode_disables_timer_removes_units_and_reloads_systemd(monkeypatch):
    from scheduler.manage_systemd import uninstall_systemd_units

    calls: list[tuple[str, object]] = []

    monkeypatch.setattr("os.geteuid", lambda: 0)

    def fake_run(command, check):
        calls.append(("run", (command, check)))

    def fake_unlink(self, missing_ok=False):
        calls.append(("unlink", (self, missing_ok)))

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(Path, "unlink", fake_unlink)

    uninstall_systemd_units()

    assert calls == [
        (
            "run",
            (["systemctl", "disable", "--now", "network-crawl.timer"], True),
        ),
        (
            "unlink",
            (Path("/etc/systemd/system/network-crawl.timer"), True),
        ),
        (
            "unlink",
            (Path("/etc/systemd/system/network-crawl.service"), True),
        ),
        ("run", (["systemctl", "daemon-reload"], True)),
    ]


def test_manage_systemd_script_runs_from_repo_root_without_import_error():
    result = subprocess.run(
        ["python", "scheduler/manage_systemd.py", "--render"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert "ModuleNotFoundError: No module named 'config'" not in result.stderr
