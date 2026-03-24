# Systemd Automation Design

## Goal

Reduce the manual Linux deployment steps for `systemd` by letting the project generate ready-to-install unit files and optionally install them with one command.

## Chosen Approach

Add a dedicated helper script at `scheduler/manage_systemd.py` that reads project settings, renders the existing `scheduler/network-crawl.service` and `scheduler/network-crawl.timer` templates into concrete unit files, writes them to `output/systemd/`, and optionally installs them into `/etc/systemd/system/`.

## Why This Approach

- It keeps deployment automation separate from the runtime entrypoint in `main.py`.
- It reuses the existing checked-in `systemd` templates instead of inventing a second source of truth.
- It supports both safe preview and one-shot install, which fits local setup and server provisioning.

## Scope

- Add a script that renders project-specific `systemd` unit files
- Use project path, Python path, current user/group, and configured timezone to fill placeholders
- Support preview generation into `output/systemd/`
- Support install mode that copies units to `/etc/systemd/system/` and runs `systemctl` setup commands
- Update docs and tests for the new deployment flow

## Non-Goals

- Managing or editing `.env` automatically
- Supporting non-systemd schedulers
- Replacing the committed template files with generated files
- Adding a daemon or long-running installer service

## Command Model

The new script should support two primary modes:

- `--render`: render concrete `network-crawl.service` and `network-crawl.timer` files into `output/systemd/`
- `--install`: render units, copy them into `/etc/systemd/system/`, then run `systemctl daemon-reload` and `systemctl enable --now network-crawl.timer`

The intended user flow is:

```bash
uv run python scheduler/manage_systemd.py --render
sudo uv run python scheduler/manage_systemd.py --install
```

This keeps a preview-first path while still allowing a single install command when the user is ready.

## Data Sources

The script should derive the concrete values from local runtime context:

- `<PROJECT_ROOT>` from the repository root
- `<PYTHON_BIN>` from `sys.executable`
- `<SERVICE_USER>` and `<SERVICE_GROUP>` from the current OS user and primary group
- `<SCHEDULE_TIMEZONE>` from `Settings.from_env()`

This avoids asking the user to hand-edit placeholders in normal cases.

## Error Handling

- `--render` should fail with a clear message if settings cannot be loaded or if templates are missing
- `--install` should fail early when not run as root, with a message that explicitly recommends `sudo`
- `systemctl` command failures should surface as readable errors instead of raw tracebacks where practical
- Invalid timezone values should continue to be caught through existing config validation

## Architecture Notes

The committed files under `scheduler/` remain templates and continue to serve as the documentation-backed source of truth. `scheduler/manage_systemd.py` becomes the automation layer on top of those templates, not a replacement for them.

Rendering should stay simple string replacement because the templates only have a small fixed set of placeholders. There is no need for a separate templating engine.

## Testing Strategy

- Add scheduler tests that verify rendered unit content substitutes placeholders with concrete values
- Add tests for install-mode command sequencing without invoking real `systemctl`
- Add tests for root-check behavior in install mode
- Update README expectations to document the automated flow as the primary path

## Risks And Mitigations

- Automatically deriving user/group could be surprising on multi-user systems; mitigate by documenting that install commands should be run as the intended service account or with explicit overrides later if needed.
- Install mode touches privileged paths; mitigate with a strict root check and preview-first documentation.
- Template drift could break rendering; mitigate by keeping placeholder names stable and covering them with tests.
