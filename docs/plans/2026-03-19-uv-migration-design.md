# UV Migration Design

## Goal

Use `uv` as the single dependency and environment manager for this project without restructuring the app into an installable package.

## Chosen Approach

Adopt a minimal `pyproject.toml` with PEP 621 project metadata, runtime dependencies under `[project.dependencies]`, and test tooling under `[dependency-groups.dev]`. Keep `main.py` and `scheduler/manage_cron.py` as direct script entrypoints, and update docs to use `uv sync` and `uv run ...` commands.

## Why This Approach

- It keeps the current workflow recognizable while replacing `venv + pip install -r requirements.txt` with one `uv` workflow.
- It avoids unnecessary packaging work such as console scripts or module reorganization.
- It makes deployments more reproducible through `uv.lock` while keeping local runs simple.

## Scope

- Add `pyproject.toml`
- Generate `uv.lock`
- Update `.gitignore` for `.venv`
- Update `README.md` install, run, test, and cron examples to use `uv`
- Remove `requirements.txt` so dependencies have one source of truth

## Non-Goals

- Turning the project into a published package
- Adding a CLI wrapper like `uv run network-crawl`
- Changing runtime behavior of the crawler, summarizer, or scheduler

## Risks And Mitigations

- `cron` still needs a concrete Python executable; docs will keep using `.venv/bin/python` for scheduled jobs.
- Removing `requirements.txt` can break old instructions; README and tests will be updated together.
- `uv` lock generation depends on the tool being installed locally; verify it before claiming completion.
