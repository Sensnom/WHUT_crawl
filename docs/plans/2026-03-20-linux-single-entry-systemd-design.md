# Linux Single-Entry Systemd Design

## Goal

Keep `main.py` as the only runtime entrypoint while making the project easier to reuse across Linux machines and safer to deploy on a Raspberry Pi with `systemd timer` as the primary scheduler.

## Chosen Approach

Retain a single executable entrypoint in `main.py`, but move orchestration and business responsibilities into smaller modules grouped by role. Keep all secrets in the local `.env`, keep path discovery rooted at `PROJECT_ROOT`, and add Linux `systemd` unit files under `scheduler/` so scheduled runs call `main.py` without duplicating business logic in the scheduler layer.

## Why This Approach

- It preserves the current user workflow: local runs and scheduled runs still execute `python main.py`.
- It reduces coupling inside `main.py`, which currently mixes CLI behavior, scheduling decisions, delivery logic, file output, and error handling.
- It makes Linux deployment more repeatable because `systemd` can own scheduling, working directory, restart policy, and logs while Python keeps control of application behavior.
- It avoids over-design for a project that only needs to run on Linux and does not need a Raspberry-Pi-specific folder structure.

## Scope

- Keep `main.py` as the sole runtime entrypoint
- Add mode-based execution so one entrypoint can run full or partial workflows
- Extract orchestration and service logic out of `main.py`
- Keep `.env` loading from project root and do not touch the real `.env`
- Add `systemd` service and timer templates under `scheduler/`
- Update docs so Linux deployment defaults to `systemd timer`
- Keep cron support as a compatibility path

## Non-Goals

- Converting the project into a packaged CLI application
- Adding Docker as the primary deployment target
- Splitting runtime behavior into multiple top-level executables
- Removing existing cron tooling
- Replacing `.env` with a separate secrets manager

## Architecture

### Entry Model

`main.py` remains the only command the user or scheduler runs. Its responsibility narrows to argument parsing, settings loading, runtime object creation, mode dispatch, top-level exception handling, and exit codes.

### Internal Layers

- `app/` holds orchestration functions such as full daily runs, single-mode runs, and health checks.
- `services/` holds domain logic for news delivery, course-task delivery, backfill handling, and cleanup.
- `adapters/` isolates integrations such as notice crawling, course-page browser automation, email delivery, and DeepSeek summarization.
- `storage/` holds persistent state logic such as delivery-state reads and writes.

This keeps deployment details out of the business layer and keeps external-system volatility, especially Playwright on ARM Linux, isolated behind narrower interfaces.

### Mode Model

`main.py` should support a default full run plus explicit modes such as `run`, `news`, `course`, `backfill`, `cleanup`, and `healthcheck`. The default invocation stays aligned with current behavior, while mode flags improve diagnostics and targeted testing without introducing more entrypoints.

### Configuration Model

The project continues to read `.env` from `PROJECT_ROOT` through `config.py`. The committed `.env.example` remains the source of documented variables. Sensitive values such as API keys, SMTP app passwords, and Smart WHUT credentials remain local-only and must not be removed or overwritten during the refactor.

Validation should become mode-aware where practical so a health check can report missing values precisely and partial workflows are not forced to require unrelated credentials.

### Linux Scheduling Model

Linux scheduling should move from cron-first documentation to `systemd`-first documentation. Two files in `scheduler/` should describe the deployment path:

- `network-crawl.service` defines working directory, executable path, and one-shot execution of `main.py`
- `network-crawl.timer` triggers the service at the configured noon and evening schedule points

`systemd` should not duplicate schedule-slot business logic. It only launches `main.py`; the application still decides whether the current run is noon, evening, manual, retry, or backfill.

### Paths And Outputs

All runtime file paths should continue to derive from `PROJECT_ROOT` or configured output paths, never from the caller's current shell directory. Runtime artifacts stay under `output/`, including summaries, delivery state, and any fallback log files.

### Error Handling

Top-level errors remain centralized in `main.py`, but service-level failures should stay isolated so course-task delivery and news delivery can fail independently when possible. Health checks should surface deployment blockers such as invalid `.env`, missing writable output directories, or unavailable Playwright browser dependencies.

## Testing Strategy

- Extend `tests/test_main.py` to lock in mode dispatch, default single-entry behavior, and health-check behavior
- Extend `tests/test_config.py` to cover any new mode-aware validation behavior
- Add scheduler tests for new `systemd` resources and keep existing cron tests passing
- Run focused regression tests around entrypoint behavior, scheduler docs/resources, and config validation before claiming completion

## Risks And Mitigations

- The refactor can break existing tests that import helpers directly from `main.py`; mitigate by extracting code incrementally and keeping compatibility wrappers until tests move.
- `systemd timer` cannot read dynamic values from `.env` by itself; mitigate by letting `systemd` only launch `main.py` and keeping schedule decisions in Python.
- Playwright on Raspberry Pi can still fail due to browser/runtime dependencies; mitigate with a dedicated `healthcheck` mode that verifies browser startup before production scheduling.
- Moving logic out of `main.py` can create circular imports; mitigate by keeping module boundaries narrow and directing dependencies inward toward services and adapters.
