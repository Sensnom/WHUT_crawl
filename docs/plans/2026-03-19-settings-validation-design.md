# Settings Validation Design

## Goal

Make configuration loading fail fast with clear, actionable error messages so bad `.env` values are caught at startup instead of surfacing later during cron runs or email delivery.

## Chosen Approach

Adopt a two-phase configuration flow inside `config.py`: `Settings.from_env()` loads raw environment values and performs basic type conversion, then a centralized validation step checks required fields, numeric ranges, timezone validity, and simple path rules before returning a usable `Settings` instance.

## Why This Approach

- It keeps configuration behavior in one place without introducing extra loader classes.
- It separates parsing from validation, which makes the code easier to test and extend.
- It gives every entrypoint the same fail-fast behavior because both `main.py` and `scheduler/manage_cron.py` already rely on `Settings.from_env()`.

## Scope

- Keep `Settings` as the single configuration object
- Add centralized validation for required fields, numeric fields, ranges, and timezone
- Replace raw conversion errors with clear configuration errors
- Update tests to lock in the new failure behavior

## Non-Goals

- Making SMTP settings mandatory for every command at config load time
- Adding a separate configuration package or loader/validator class hierarchy
- Changing runtime delivery logic beyond earlier validation and clearer errors

## Validation Rules

- `DEEPSEEK_API_KEY` must be non-empty
- `REQUEST_TIMEOUT`, `MAX_PAGES`, `BACKFILL_MAX_DAYS`, and `STATE_RETENTION_DAYS` must be integers greater than zero
- `SMTP_PORT` must be an integer in the range `1-65535`
- `SCHEDULE_HOUR` and `EVENING_SCHEDULE_HOUR` must be integers in the range `0-23`
- `SCHEDULE_MINUTE` and `EVENING_SCHEDULE_MINUTE` must be integers in the range `0-59`
- `SCHEDULE_TIMEZONE` must resolve through `zoneinfo.ZoneInfo`
- `OUTPUT_DIR` must not be blank

## Error Handling

- Configuration failures should raise a dedicated, human-readable error instead of leaking `ValueError` from `int(...)`
- Multiple invalid settings should be reported together when practical so users can fix the file in one edit
- Entrypoints should print the configuration error and exit with status `1`

## Risks And Mitigations

- Stricter validation can break previously tolerated bad `.env` values; mitigate this with explicit tests and clear messages.
- Aggregating multiple errors adds a little complexity; keep the validation helper small and limited to current fields.
- Future config fields could bypass validation; mitigate by keeping all parsing and validation in `config.py` and extending tests when fields are added.
