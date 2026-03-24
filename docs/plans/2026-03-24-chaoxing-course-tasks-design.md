# Chaoxing Course Tasks Design

## Goal

Add Chaoxing task crawling for selected courses, then merge Chaoxing unfinished assignments and exams into the existing Xiaoya course-task notification.

## Chosen Approach

Keep the current Xiaoya task flow intact, then add a separate Chaoxing crawling path with its own settings, login state file, client, parser, and service helpers. Merge both platforms into one unified `CourseTask` list before building the existing course-task email and artifact.

## Why This Approach

- It avoids coupling Chaoxing login behavior to the existing Smart WHUT flow in `course_client.py`.
- It keeps Playwright auth state isolated so one platform cannot break the other.
- It preserves the current user-facing behavior of receiving one course-task email instead of multiple partial notifications.

## Scope

- Add Chaoxing-specific environment variables for base URL, username, password, target course names, and service toggle.
- Read target course names from `.env` and normalize them into a list.
- Log into `https://i.chaoxing.com/base?ws=1` with a separate Playwright auth state cache.
- Open each configured course, enter the assignment and exam sections, and collect unfinished items.
- Filter Chaoxing items to only those due within the next 30 days.
- Merge Xiaoya and Chaoxing results into one course-task email and one course-task artifact.
- Degrade gracefully when one source fails but the other still returns usable tasks.
- Add tests and docs for the new behavior.

## Non-Goals

- Replacing the current Xiaoya crawler.
- Sending Chaoxing in a separate email channel.
- Supporting every Chaoxing module beyond assignments and exams.
- Implementing fuzzy course-name matching or automatic course discovery configuration.

## Configuration Model

Add these settings:

- `CHAOXING_BASE_URL`, defaulting to `https://i.chaoxing.com/base?ws=1`
- `CHAOXING_USERNAME`
- `CHAOXING_PASSWORD`
- `CHAOXING_TARGET_COURSE_NAMES`, a comma-separated course-name list
- `ENABLE_CHAOXING_SERVICE`, defaulting to `true`

`Settings.from_env()` should strip whitespace, split the course-name list, and ignore empty entries so the service can safely operate on a clean `list[str]`.

## Data Model

Extend `CourseTask` so the email layer can distinguish source and task type without special-case branching elsewhere. The model should carry at least:

- title
- course_name
- deadline_text
- deadline_at
- url
- `source_platform` such as `xiaoya` or `chaoxing`
- `task_type` such as `task`, `assignment`, or `exam`

This keeps the merged email rendering simple and lets the service sort or group items consistently.

## Crawl Flow

The Chaoxing flow should be isolated in a new `chaoxing_client.py`:

1. Open the Chaoxing base page with Playwright.
2. Reuse a dedicated storage-state file such as `output/chaoxing_auth_state.json` when available.
3. If cached login is invalid, perform an interactive login with `CHAOXING_USERNAME` and `CHAOXING_PASSWORD`.
4. Read the visible course list and only enter courses whose names match `CHAOXING_TARGET_COURSE_NAMES`.
5. For each selected course:
   - open the course homepage
   - enter the assignment section and collect unfinished assignments
   - enter the exam section and collect unfinished exams
6. Normalize the collected entries into unified `CourseTask` objects.
7. Save the refreshed Chaoxing storage state for later runs.

## Filtering Rules

The Chaoxing parser or service layer should enforce these rules:

- Include only configured target courses.
- Include only unfinished assignments.
- Include only unfinished exams.
- Include only items with a parseable deadline.
- Include only items whose deadline falls within `[now, now + 30 days]`.

Items without deadlines should be skipped to avoid noisy historical tasks or permanently-open content appearing in reminders.

## Merge And Delivery Behavior

The current course-task email path should remain the single delivery path. `fetch_course_tasks()` should become an aggregator:

- fetch Xiaoya tasks
- fetch Chaoxing tasks when Chaoxing is enabled and configured
- merge and sort the combined list

The email subject can remain unchanged. The body and HTML should group items by platform and, for Chaoxing, by task type so the user can quickly see:

- Xiaoya tasks
- Chaoxing assignments
- Chaoxing exams

Artifact writing should still produce one file such as `output/course_tasks_YYYYMMDD_noon.md`, now containing both platforms.

## Error Handling

- If Xiaoya fails but Chaoxing succeeds, still send the merged email with Chaoxing content and include a short Xiaoya failure note.
- If Chaoxing fails but Xiaoya succeeds, still send the merged email with Xiaoya content and include a short Chaoxing failure note.
- If both fail, preserve the existing failure-recording behavior.
- If Chaoxing credentials or target course names are missing, Chaoxing should quietly skip instead of failing the entire course-task pipeline.

This keeps the reminder channel resilient and avoids losing all notifications because one platform changed its UI.

## Architecture Notes

`services/course_service.py` should own the cross-platform aggregation, not the email layer. The email builder should only render the already-normalized merged task list.

Chaoxing-specific selectors and DOM parsing should stay out of `course_client.py` and `course_parser.py` as much as possible. Shared task rendering should depend on the unified `CourseTask` model, not on crawler-specific conditionals.

## Testing Strategy

- Extend config tests for the new Chaoxing settings and parsed course-name list.
- Add parser tests for unfinished assignment and exam extraction plus 30-day filtering.
- Add client tests with fake Playwright pages to verify login reuse, target-course selection, and section traversal.
- Add service tests that verify Xiaoya-plus-Chaoxing merging and partial-failure behavior.
- Update email-rendering tests if needed so grouped output remains stable.
- Update README expectations for the new `.env` fields and merged notification behavior.

## Risks And Mitigations

- Chaoxing selectors may differ between accounts or course UIs; mitigate by isolating selectors in one client and covering them with focused tests.
- A single shared artifact could hide source-specific errors; mitigate by including failure notes in the rendered output.
- Incorrect course-name parsing from `.env` could silently skip work; mitigate by trimming entries and testing empty-value behavior.
