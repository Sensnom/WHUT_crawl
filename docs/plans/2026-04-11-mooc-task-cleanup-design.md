# MOOC Task Cleanup Design

## Goal

Make MOOC reminders usable by cleaning noisy task titles and only keeping tasks whose deadlines fall within the next 30 days.

## Scope

- Only change MOOC task parsing in `mooc_client.py`
- Do not change Xiaoya or Chaoxing filtering behavior
- Do not change email templates

## Design

1. Add MOOC-specific deadline parsing that normalizes `YYYY/MM/DD HH:MM` and `YYYY-MM-DD HH:MM` into a standard `deadline_text` plus `deadline_at`.
2. Filter MOOC tasks inside the MOOC client so only tasks with parseable deadlines in the range `now <= deadline <= now + 30 days` are returned.
3. Clean noisy fallback titles by removing embedded time strings and UI copy such as `时间：`, `前往测验`, and `请注意`, then prefer compact labels like `作业` or `考试` when that is all the page exposes.
4. Keep the change minimal and local so existing email rendering and task aggregation continue to work unchanged.

## Tests

- Verify noisy MOOC fallback titles are cleaned
- Verify MOOC deadlines are parsed into `deadline_at`
- Verify past tasks are filtered out
- Verify tasks beyond 30 days are filtered out
- Verify near-future tasks are kept
