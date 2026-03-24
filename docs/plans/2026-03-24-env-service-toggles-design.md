# Env Service Toggles Design

## Goal

Allow the runtime to enable or disable the news-delivery flow and the course-task-delivery flow through `.env` so one deployment can selectively run only the services it needs.

## Chosen Approach

Add two boolean settings in `config.py`: `ENABLE_NEWS_SERVICE` and `ENABLE_COURSE_SERVICE`, both defaulting to `true`. Route all top-level workflow decisions through those settings inside `app/workflows.py` so disabled services are skipped before their related delivery steps run.

## Why This Approach

- It matches the requested granularity exactly: one switch for news, one switch for course tasks.
- It keeps service selection in configuration instead of adding more CLI modes or separate entrypoints.
- It is backward-compatible because existing deployments continue to run both services unless the new flags are explicitly changed.

## Scope

- Add two `.env`-driven service toggles
- Parse and validate boolean values centrally in `config.py`
- Make the daily workflow skip disabled service branches
- Treat the news toggle as controlling the entire news pipeline: normal sends, retries, and backfill
- Update docs and tests to lock in the behavior

## Non-Goals

- Adding finer-grained toggles for cleanup, backfill, or retry as separate features
- Adding per-mode CLI flags for service selection
- Changing email content, schedule rules, or state-file structure beyond what is needed for the toggle behavior

## Configuration Model

Two new environment variables are added:

- `ENABLE_NEWS_SERVICE=true`
- `ENABLE_COURSE_SERVICE=true`

Accepted values should be common boolean spellings such as `true/false`, `1/0`, and `yes/no`, with invalid values raising a clear configuration error. Defaults stay `true` so existing `.env` files remain valid without edits.

## Runtime Behavior

When `ENABLE_NEWS_SERVICE=false`, the runtime should skip all news-specific orchestration:

- today's failed news retry
- news backfill generation and sending
- noon or evening news delivery

When `ENABLE_COURSE_SERVICE=false`, the runtime should skip course-task delivery entirely.

The workflow can still start and exit successfully if one or both services are disabled. If both are disabled, the program becomes a no-op run with no delivery side effects.

## Architecture Notes

`config.py` remains the single source of truth for env parsing. `app/workflows.py` remains the place where orchestration decisions happen. This keeps the toggle logic at the boundary between configuration and workflow, without pushing conditionals down into each delivery helper.

That boundary is important because the news toggle needs to cover several related steps together. Gating only `process_news_run()` would be incomplete because retries and backfill are triggered earlier in the workflow.

## Testing Strategy

- Extend `tests/test_config.py` to cover boolean parsing defaults, accepted false values, and invalid boolean errors
- Extend `tests/test_main.py` or workflow tests to verify disabled news skips retry, backfill, and news send
- Extend tests to verify disabled course service skips course-task delivery while leaving news behavior intact
- Verify mixed configurations where only one service is enabled

## Risks And Mitigations

- Invalid boolean strings could silently misconfigure a deployment; mitigate with strict parsing and clear errors.
- Gating only part of the news flow could leave retries or backfill active by mistake; mitigate by placing the decision in `app/workflows.py` before any news-specific step executes.
- Future service toggles could create scattered conditionals; mitigate by keeping toggle checks centralized in the orchestrator.
