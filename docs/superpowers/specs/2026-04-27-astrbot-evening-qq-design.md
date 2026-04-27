# AstrBot Evening QQ Delivery Design

## Goal

Send the daily school news summary to QQ through AstrBot once per evening run while keeping the existing email flow unchanged.

## Scope

- Add an optional AstrBot outbound channel for news delivery only
- Only send the QQ message during the evening news run
- Keep noon news email behavior unchanged
- Keep course task delivery email-only
- Keep backfill email-only for now

## Chosen Approach

Use AstrBot's `POST /api/v1/im/message` API as a second outbound channel that hangs off the existing evening news delivery path.

The evening workflow will continue to build the normal summary Markdown file first. After the evening email succeeds or fails, the same notice data will be formatted into a QQ-friendly plain text message and sent to AstrBot when the AstrBot channel is enabled.

This keeps the current summary generation logic, avoids coupling to NapCat-specific APIs, and limits the new behavior to one delivery slot.

## Why This Approach

- AstrBot already exposes a documented authenticated HTTP API and can forward to QQ through the user's existing bot setup.
- The current codebase already separates content generation from transport enough to add one more sender without rewriting the whole delivery stack.
- Restricting QQ delivery to the evening slot matches the requested behavior and avoids touching noon and course-task flows.
- Formatting a dedicated QQ message is safer than sending raw Markdown with inline links because QQ rendering is less predictable than email or file output.

## Configuration

Add these settings:

- `ENABLE_ASTRBOT_SERVICE`: boolean toggle, default `false`
- `ASTRBOT_BASE_URL`: defaults to `http://localhost:6185`
- `ASTRBOT_API_KEY`: AstrBot API key with `im` scope
- `ASTRBOT_UMO`: target unified message origin, such as `onebot:group:123456789`

Validation rules:

- If `ENABLE_ASTRBOT_SERVICE` is `false`, AstrBot settings may be blank.
- If `ENABLE_ASTRBOT_SERVICE` is `true`, require non-empty base URL, API key, and UMO.
- Keep AstrBot validation separate from SMTP validation so one channel can fail configuration without changing the other channel's rules.

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

- Extend `Settings` with AstrBot fields and env parsing.
- Add AstrBot-specific validation helper.
- Keep existing mode validation behavior for email intact.

### `astrbot_sender.py`

Add a dedicated sender module responsible for:

- building the request URL from `ASTRBOT_BASE_URL`
- sending `POST /api/v1/im/message`
- authenticating with `Authorization: Bearer ...`
- raising a clear runtime error on non-2xx responses or malformed replies

This module should stay transport-focused and should not know how summaries are assembled.

### `services/news_service.py`

Update only the evening delivery flow:

- continue collecting notices using the existing noon-versus-evening diff logic
- continue writing the evening summary artifact
- continue sending the evening email as today
- if AstrBot is enabled, build the QQ message from the same `new_notices` set and send it through the new sender

QQ delivery should not run in:

- `process_noon_delivery`
- course task services
- backfill services

### Delivery state and logging

Extend news delivery records with AstrBot-specific fields:

- `astrbot_sent`: boolean
- `astrbot_error`: string

Behavior:

- Email failure must not suppress an AstrBot attempt.
- AstrBot failure must not overwrite email success.
- Evening record status remains based on the overall news run, while channel-specific fields show which sender failed.
- Add concise trace output for AstrBot request start and result, including HTTP status details when available.

## Error Handling

- If no new evening notices exist, keep the current skip behavior and do not call AstrBot.
- If email sending fails, still attempt AstrBot sending for the same evening content.
- If AstrBot sending fails, save the evening record with `astrbot_sent = false` and the error message.
- If AstrBot is disabled, record `astrbot_sent = false` and leave `astrbot_error` empty.

## Testing Strategy

Add focused unit tests for:

- AstrBot settings validation when enabled versus disabled
- QQ message formatting from summary inputs and notice lists
- AstrBot request payload construction
- evening delivery calling AstrBot only in the evening path
- evening delivery still attempting AstrBot when email sending fails
- noon delivery never calling AstrBot

Do not add a live integration test against a running AstrBot instance.

## Non-Goals

- Replacing SMTP with AstrBot
- Sending course task reminders to QQ
- Sending noon summaries to QQ
- Sending backfill summaries to QQ
- Adding NapCat-specific direct transport support
- Sending files, images, or rich message segments in the first version
