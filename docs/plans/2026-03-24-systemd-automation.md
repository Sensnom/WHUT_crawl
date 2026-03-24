# Systemd Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automate `systemd` deployment by rendering ready-to-install unit files and supporting one-command installation.

**Architecture:** Keep `scheduler/network-crawl.service` and `scheduler/network-crawl.timer` as the checked-in templates, then add `scheduler/manage_systemd.py` to render those templates with local runtime values. Let `--render` write preview files into `output/systemd/`, and let `--install` reuse the same rendered content before copying into `/etc/systemd/system/` and running the required `systemctl` commands.

**Tech Stack:** Python 3.10+, pathlib, argparse, shutil, subprocess, pwd, grp, pytest, Markdown documentation

---

### Task 1: Add failing tests for rendered unit generation

**Files:**
- Modify: `tests/test_scheduler.py`
- Create: `scheduler/manage_systemd.py`

**Step 1: Write the failing test**

```python
def test_rendered_service_file_replaces_template_placeholders(tmp_path):
    from scheduler.manage_systemd import render_service_template

    rendered = render_service_template(
        project_root="/srv/network-crawl",
        python_bin="/srv/network-crawl/.venv/bin/python",
        service_user="crawler",
        service_group="crawler",
    )

    assert "<PROJECT_ROOT>" not in rendered
    assert 'WorkingDirectory=/srv/network-crawl' in rendered
    assert 'ExecStart="/srv/network-crawl/.venv/bin/python" "/srv/network-crawl/main.py"' in rendered
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scheduler.py::test_rendered_service_file_replaces_template_placeholders -v`
Expected: FAIL because `scheduler/manage_systemd.py` and render helpers do not exist yet.

**Step 3: Write minimal implementation**

Add template-loading and placeholder-replacement helpers in `scheduler/manage_systemd.py` for both service and timer templates.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scheduler.py::test_rendered_service_file_replaces_template_placeholders -v`
Expected: PASS.

### Task 2: Add failing tests for render command output files

**Files:**
- Modify: `tests/test_scheduler.py`
- Modify: `scheduler/manage_systemd.py`

**Step 1: Write the failing test**

```python
def test_render_command_writes_units_to_output_directory(tmp_path):
    from scheduler.manage_systemd import write_rendered_units

    paths = write_rendered_units(
        output_dir=tmp_path,
        service_text="[Service]\nWorkingDirectory=/srv/app\n",
        timer_text="[Timer]\nTimezone=Asia/Shanghai\n",
    )

    assert paths["service"].read_text(encoding="utf-8").startswith("[Service]")
    assert paths["timer"].read_text(encoding="utf-8").startswith("[Timer]")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scheduler.py::test_render_command_writes_units_to_output_directory -v`
Expected: FAIL because the write helper does not exist yet.

**Step 3: Write minimal implementation**

Implement a helper that creates `output/systemd/` and writes `network-crawl.service` and `network-crawl.timer` there.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scheduler.py::test_render_command_writes_units_to_output_directory -v`
Expected: PASS.

### Task 3: Add failing tests for install-mode safety and command flow

**Files:**
- Modify: `tests/test_scheduler.py`
- Modify: `scheduler/manage_systemd.py`

**Step 1: Write the failing test**

```python
def test_install_mode_requires_root(monkeypatch, tmp_path):
    from scheduler.manage_systemd import install_rendered_units

    monkeypatch.setattr("os.geteuid", lambda: 1000)

    with pytest.raises(PermissionError, match="sudo"):
        install_rendered_units(
            rendered_service_path=tmp_path / "network-crawl.service",
            rendered_timer_path=tmp_path / "network-crawl.timer",
        )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scheduler.py::test_install_mode_requires_root -v`
Expected: FAIL because install helpers and root checks do not exist yet.

**Step 3: Extend the failing test set**

Add a second focused test that mocks file copies and `subprocess.run`, then verifies install mode executes these steps in order:
- copy service file
- copy timer file
- `systemctl daemon-reload`
- `systemctl enable --now network-crawl.timer`

**Step 4: Write minimal implementation**

Implement install helpers that enforce root, copy rendered files into `/etc/systemd/system/`, and run the two `systemctl` commands.

**Step 5: Run targeted tests**

Run: `uv run pytest tests/test_scheduler.py::test_install_mode_requires_root -v`
Expected: PASS.

### Task 4: Add a small CLI around render and install helpers

**Files:**
- Modify: `scheduler/manage_systemd.py`
- Modify: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
def test_manage_systemd_parse_args_supports_render_and_install():
    from scheduler.manage_systemd import parse_args

    args = parse_args(["--render"])

    assert args.render is True
    assert args.install is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scheduler.py::test_manage_systemd_parse_args_supports_render_and_install -v`
Expected: FAIL because the CLI parser does not exist yet.

**Step 3: Write minimal implementation**

Add `argparse` handling plus a `main()` function that:
- loads `Settings.from_env()`
- derives concrete values from the local machine
- renders units
- writes preview files for `--render`
- performs installation for `--install`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scheduler.py::test_manage_systemd_parse_args_supports_render_and_install -v`
Expected: PASS.

### Task 5: Document the new automated deployment flow

**Files:**
- Modify: `README.md`
- Modify: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_readme_documents_manage_systemd_commands():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "manage_systemd.py --render" in readme
    assert "manage_systemd.py --install" in readme
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_smoke.py::test_readme_documents_manage_systemd_commands -v`
Expected: FAIL because the README still documents manual unit editing and copying as the primary path.

**Step 3: Write minimal implementation**

Update the README so the primary deployment flow is:
- render preview files
- install with one `sudo` command
- optionally inspect generated files under `output/systemd/`

Keep the checked-in templates documented as the source templates, not the files users usually edit directly.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_smoke.py::test_readme_documents_manage_systemd_commands -v`
Expected: PASS.

### Task 6: Run focused regression checks

**Files:**
- Verify: `scheduler/manage_systemd.py`
- Verify: `scheduler/network-crawl.service`
- Verify: `scheduler/network-crawl.timer`
- Verify: `README.md`
- Verify: `tests/test_scheduler.py`
- Verify: `tests/test_smoke.py`

**Step 1: Run focused tests**

Run: `uv run pytest tests/test_scheduler.py tests/test_smoke.py -v`
Expected: PASS.

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS.

**Step 3: Manually review command examples**

Confirm the documented commands are:

```bash
uv run python scheduler/manage_systemd.py --render
sudo uv run python scheduler/manage_systemd.py --install
```

and that install mode is documented as root-only.
