# NapCat Evening QQ Delivery Design

## Goal

Send the daily school news summary to QQ through NapCat once per evening run while keeping the existing email flow unchanged.

## Scope

- Add an optional NapCat outbound channel for news delivery only
- Only send the QQ message during the evening news run
- Keep noon news email behavior unchanged
- Keep course task delivery email-only
- Keep backfill email-only for now
- Support multiple QQ targets in one run, including groups and private chats

## Chosen Approach

Use NapCat's HTTP API as a second outbound channel that hangs off the existing evening news delivery path.

The evening workflow will continue to build the normal summary Markdown file first. After the evening email succeeds or fails, the same notice data will be formatted into a QQ-friendly plain text message and sent to each configured NapCat target when the NapCat channel is enabled.

This keeps the current summary generation logic, avoids coupling delivery to another relay layer, and limits the new behavior to one delivery slot.

## Why This Approach

- NapCat is already available in the user's environment and is a direct fit for QQ delivery.
- The current codebase already separates content generation from transport enough to add one more sender without rewriting the whole delivery stack.
- Restricting QQ delivery to the evening slot matches the requested behavior and avoids touching noon and course-task flows.
- Formatting a dedicated QQ message is safer than sending raw Markdown with inline links because QQ rendering is less predictable than email or file output.
- A multi-target configuration supports both groups and private chats without requiring multiple separate feature branches.

## Configuration

Add these settings:

- `ENABLE_NAPCAT_SERVICE`: boolean toggle, default `false`
- `NAPCAT_BASE_URL`: NapCat HTTP base URL
- `NAPCAT_ACCESS_TOKEN`: NapCat access token
- `NAPCAT_TARGETS`: comma-separated target list, such as `group:123456789,private:987654321`

Validation rules:

- If `ENABLE_NAPCAT_SERVICE` is `false`, NapCat settings may be blank.
- If `ENABLE_NAPCAT_SERVICE` is `true`, require non-empty base URL, access token, and at least one valid target.
- Each target must use `group:<id>` or `private:<id>` format.
- Keep NapCat validation separate from SMTP validation so one channel can fail configuration without changing the other channel's rules.

## Message Format

QQ delivery should stay close to the existing summary file structure, but use light formatting and line breaks instead of Markdown-heavy syntax.

Target shape:

```text
本科生院最近三天通知总结

摘要
1. ...
2. ...
3. ...

涉及通知
1. 关于xxx的通知
http://i.whut.edu.cn/...

2. 关于yyy的通知
http://i.whut.edu.cn/...
```

Formatting rules:

- Do not send `#` or `##` headings.
- Do not send inline Markdown links like `[title](url)`.
- Keep blank lines between sections for readability.
- Put each URL on its own line so QQ clients can open it reliably.
- If there are no notices, send the same lightweight structure with `最近三天没有通知。`.

## Code Changes

### `config.py`

- Extend `Settings` with NapCat fields and env parsing.
- Add NapCat-specific validation helper.
- Add parsing for `NAPCAT_TARGETS` into a normalized target list.
- Keep existing mode validation behavior for email intact.

### `napcat_sender.py`

Add a dedicated sender module responsible for:

- building request URLs from `NAPCAT_BASE_URL`
- choosing the correct HTTP endpoint or payload shape for group versus private targets
- authenticating with the NapCat access token
- sending one target at a time and returning per-target success or failure details
- raising a clear runtime error for malformed responses, while allowing the caller to continue sending to other targets

This module should stay transport-focused and should not know how summaries are assembled.

### `services/news_service.py`

Update only the evening delivery flow:

- continue collecting notices using the existing noon-versus-evening diff logic
- continue writing the evening summary artifact
- continue sending the evening email as today
- if NapCat is enabled, build the QQ message from the same `new_notices` set and send it through the new sender to every configured target

QQ delivery should not run in:

- `process_noon_delivery`
- course task services
- backfill services

### Delivery state and logging

Extend news delivery records with NapCat-specific fields:

- `napcat_sent`: boolean, `true` only when all configured targets succeed
- `napcat_error`: string summary of failed targets
- `napcat_target_results`: list of per-target results

Each per-target result should contain:

- `target`: normalized string such as `group:123456789`
- `sent`: boolean
- `error`: string

Behavior:

- Email failure must not suppress NapCat attempts.
- One NapCat target failure must not suppress the remaining NapCat targets.
- NapCat failure must not overwrite email success.
- Evening record status remains based on the overall news run, while channel-specific fields show which sender failed.
- Add concise trace output for NapCat request start and result, including enough target detail to identify failures.

## Error Handling

- If no new evening notices exist, keep the current skip behavior and do not call NapCat.
- If email sending fails, still attempt NapCat sending for the same evening content.
- If one or more NapCat targets fail, save the evening record with `napcat_sent = false` and a summarized error message while preserving each target result.
- If NapCat is disabled, record `napcat_sent = false`, leave `napcat_error` empty, and store an empty target-results list.

## Testing Strategy

Add focused unit tests for:

- NapCat settings validation when enabled versus disabled
- `NAPCAT_TARGETS` parsing and rejection of malformed targets
- QQ message formatting from summary inputs and notice lists
- NapCat request payload construction for group and private targets
- evening delivery calling NapCat only in the evening path
- evening delivery still attempting all NapCat targets when email sending fails
- noon delivery never calling NapCat
- delivery-state serialization of the new NapCat result fields

Do not add a live integration test against a running NapCat instance.

## Non-Goals

- Replacing SMTP with NapCat
- Sending course task reminders to QQ
- Sending noon summaries to QQ
- Sending backfill summaries to QQ
- Multi-message batching, file uploads, or rich media in the first version
