# HTML Email Design

## Goal

Upgrade outbound notification emails from plain text only to a dual-format email with both plain text and HTML so the summary is easier to read in common mail clients while preserving compatibility.

## Updated Direction

Keep the existing SMTP sending flow and plain text fallback, but improve the HTML presentation in two ways:

- move from a bare utility layout to a cleaner card-based notification email
- render summary Markdown into readable HTML instead of showing Markdown source text directly

The result should still feel like a functional notification email rather than a marketing newsletter.

## Chosen Approach

Use a conservative card-style HTML template with inline styles only. Add a lightweight Markdown-to-HTML renderer in `email_sender.py` that supports the subset already produced by summaries and backfill content: headings, paragraphs, unordered lists, bold text, blockquotes, and horizontal separators.

## Why This Approach

- It solves the biggest readability problem: Markdown source is hard to scan in email clients.
- It keeps transport and configuration unchanged, so Gmail SMTP, QQ SMTP, and similar providers continue working.
- It avoids adding a full Markdown dependency or complex email layout system for a narrow rendering need.
- It keeps rendering logic local to the email layer instead of spreading formatting across crawl or summary code.

## Scope

- Improve daily HTML email layout with clearer spacing, hierarchy, and section cards
- Improve evening HTML email layout while preserving a distinct evening badge/state
- Improve backfill HTML email layout so each day is readable as a section, not a raw code block
- Convert supported Markdown structures in summaries and backfill sections into readable HTML
- Continue sending plain text and HTML together in every outbound email

## Non-Goals

- Adding images, logos, attachments, or remote assets
- Supporting every Markdown feature or GitHub-flavored Markdown extension
- Changing crawl, summary, deduplication, or scheduling behavior
- Adding provider-specific email rendering branches

## Visual Structure

- Outer page background with a narrow centered container for mobile readability
- Header card containing title, short context line, and message-type badge
- Summary card with rendered Markdown content
- Notice list card with title, publish date, and source link per notice
- Footer with generation time and contextual labels such as backfill date range

## Markdown Rendering Rules

The renderer should be deliberately small and safe.

- Escape all incoming content first
- Convert blank-line-separated blocks into paragraphs or list groups
- Support ATX headings such as `#` and `##`
- Support unordered list items beginning with `- ` or `* `
- Support `**bold**` inline emphasis
- Support simple blockquotes beginning with `> `
- Support `---` as a divider
- Do not support raw HTML passthrough, images, code fences, tables, or nested list complexity unless current tests require them

## Message Variants

- Noon summary: neutral badge and normal summary framing
- Evening update: explicit evening badge and wording so incremental updates are obvious
- Backfill message: explicit backfill badge, visible date range, and day-by-day sections rendered as readable prose instead of `<pre>` source blocks

## Compatibility Constraints

- Use inline styles only
- Use conservative elements such as `div`, `p`, `ul`, `li`, `strong`, and simple headings
- Avoid JavaScript, forms, remote fonts, remote images, advanced selectors, and unsupported layout tricks
- Keep all rendered HTML deterministic enough for pytest assertions

## Risks And Mitigations

- Markdown parsing can become a slippery slope; mitigate by supporting only the syntax current summaries use and locking behavior down with tests.
- HTML and text variants can drift; mitigate by building both from the same summary/notices inputs and reusing shared content assembly where practical.
- Richer styling can hurt compatibility; mitigate by staying with inline styles and simple block structure.

## Testing Strategy

- Add focused tests for Markdown summary rendering into HTML blocks and lists
- Add tests for evening and backfill variants so visual markers remain distinct
- Keep multipart email structure tests to ensure plain text fallback still ships
- Verify noon, evening, and backfill flows in `tests/test_main.py` continue to pass with HTML generation enabled
