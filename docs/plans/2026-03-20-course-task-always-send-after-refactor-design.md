# Course Task Always-Send After Refactor Design

## Goal

Make course-task email delivery run on every `main.py` execution, even if the same course-task slot has already been successfully sent earlier that day.

## Chosen Approach

Keep the course-task state record and artifact-writing behavior, but remove the duplicate-send guard from the course-task delivery path. The state file continues to store the latest send result for the day and slot, yet that record no longer blocks another course-task email from being sent.

## Why This Approach

- It matches the requested behavior directly: every run sends the course-task email.
- It keeps the change isolated to the course-task flow and does not affect the news-summary dedupe rules.
- It preserves current artifact and state-writing behavior, so the rest of the system does not need a state-model redesign.

## Scope

- Remove successful-send dedupe only for course-task delivery
- Keep course-task artifact generation and state recording
- Keep news noon/evening dedupe behavior unchanged
- Update tests to reflect the new always-send behavior

## Non-Goals

- Adding a configuration flag for switching between dedupe and always-send
- Redesigning the delivery-state store into a multi-entry send-history model
- Changing the behavior for news-summary emails

## Behavior Change

Today, `services/course_service.py` checks the existing state record for the day and course-task slot. If that record shows `email_sent=True`, it prints a duplicate-send message and returns without sending.

After the change:

- Every invocation of the course-task delivery path sends the course-task email
- The delivery record for the day and slot is still updated after each run
- The generated course-task artifact file is still written on successful sends
- Failures still record a failed status for the same day and slot

This means repeated runs on the same day will send repeated course-task emails, while the stored state remains a latest-result snapshot rather than a full send history.

## Architecture Impact

The change stays inside the course-task service boundary. `main.py`, `app/runtime.py`, and `app/workflows.py` do not need a new dispatch mode or new orchestration rule. Only the behavior inside `services/course_service.py` changes, plus tests that currently assert duplicate sends are skipped.

## Testing Strategy

- Replace the old service-level duplicate-skip test with a test that proves a previously successful same-day record does not block another send
- Keep existing integration-style tests around `main.py` course-task execution passing
- Run focused regression tests for `tests/test_course_service.py`, `tests/test_main.py`, and any other affected focused suite before claiming completion

## Risks And Mitigations

- Repeated manual runs will send repeated course-task emails by design; this is intentional and should be documented by behavior, not treated as a regression.
- Because the state store still keeps only the latest result, you will not get a per-send history for repeated runs; this is acceptable for the current request and avoids over-design.
- If you later want different behavior for manual versus scheduled runs, that should be handled as a separate feature, likely with an explicit mode-aware or config-aware policy.
