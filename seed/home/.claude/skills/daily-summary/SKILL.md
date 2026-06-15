---
name: daily-summary
description: Produce David's end-of-day work summary from GitLab activity as a markdown file uploaded to a 1-hour share link. Use when he asks for a "daily summary" or "what did I/we work on today".
---

# Daily summary

Pull today's GitLab activity for David and the bot, format it as a markdown
summary, and deliver it as a `.md` file uploaded to a 1-hour-lifetime sharing
service (see "Deliver" below).

## Gather the data

Use `glab` against `code.hoelle.games` for BOTH users:
- `david.dunnings` — user id 34
- `claude-bot` — user id 110

Fetch each user's events since the start of today. Keep the merged MRs
(`accepted MergeRequest`), review/approval activity (`commented on` a `Note`/
`DiffNote`, or `approved MergeRequest`), and anything still open. Pull
`project_id` too — review activity lives on repos David didn't necessarily
author MRs in (e.g. a slot-backend review), so you need it to attribute the
work to the right repo section:

```bash
glab api "users/34/events?after=<yesterday>&per_page=100" \
  | jq -r '.[] | "\(.created_at) | \(.action_name) | \(.target_type) | \(.project_id) | \(.target_title)"'
glab api "users/110/events?after=<yesterday>&per_page=100" | jq -r '...'
```

`project_id` is numeric — resolve each distinct one to its repo name with
`glab api "projects/<id>" | jq -r .path_with_namespace`. Collapse the multiple
comment events on a single MR into ONE review bullet (a review thread fires
several `commented on` events; they are one review, not many).

For the "Still open" section, list un-merged MRs authored by either user that
were updated today:

```bash
glab api "merge_requests?author_id=110&state=opened&scope=all&per_page=50" \
  | jq -r '.[] | select(.updated_at >= "<today>") | "\(.references.full)  \(.title)"'
glab api "merge_requests?author_id=34&state=opened&scope=all&per_page=50" | jq -r '...'
```

## Format

Section order: **General → one section per repo → Still open / in progress → Summary**.

- **General** — leading section for non-code items (meetings/calls). Leave it
  with a placeholder line or two; David fills these in himself.
- **Per repo** — one section per repo touched (`hizi-engine-sdk`, `hizi-engine`,
  `hizi-engine-creator`, `slot-backend`, `hearth`, …). A repo counts as touched
  if there was a merged MR **or** review/approval activity there. List:
  - merged MR titles, keeping the real MR/commit title text (e.g. `fix(fixed-odds): …`);
  - reviews as `Reviewed "<MR title>"` (one bullet per MR reviewed, even if the
    review spanned several comments).
  Attribute each bullet to the repo from its resolved `project_id`, not the
  repo of the day's other work.
- **Still open / in progress** — un-merged MRs as `<repo>: <description>`.
  If everything opened today was merged, say so briefly instead of leaving it blank.
- **Summary** — one paragraph: count of MRs merged, repos touched, headline themes.

## CRITICAL — formatting rules

- Section names are bold text lines (e.g. `**hearth**`) — no `#`/`##`.
- Every item is a markdown bullet: `- ` prefix, no indentation.
- NO blank line between a section name and its bullets — the bullets start on
  the very next line.
- Exactly ONE blank line between sections.

### Shape

```
**General**
- Some random calls
- Internal support for hizi engine

**hearth**
- Add Activity feed with per-user read/unread + mark-as-read
- Remove the "Staff/Client view" banner on desktop too

**hizi-engine**
- feat(gamble): never offer card/ladder gamble below stake

**slot-backend**
- Reviewed "Add useTicketFeatureType support"

**Still open / in progress**
- (nothing left open — everything opened today was merged)

**Summary**
- 14 MRs merged across 3 repos. <headline themes…>
```

## Deliver — upload as a 1-hour markdown file

Write the finished summary to `/tmp/daily-summary-<YYYY-MM-DD>.md` (exact
content and formatting as above). Then upload it to Litterbox (catbox.moe's
temporary host; anonymous, files auto-delete) with a 1-hour lifetime:

```bash
curl -sS -F "reqtype=fileupload" -F "time=1h" \
  -F "fileToUpload=@/tmp/daily-summary-<YYYY-MM-DD>.md" \
  https://litterbox.catbox.moe/resources/internals/api.php
```

The response body is the URL (e.g. `https://litter.catbox.moe/abc123.md`).
Verified working from agentbox 2026-06-10. (Alternatives tested and rejected
then: 0x0.st uploads disabled, dpaste.org API gone/405, tmpfiles.org rejects
`.md`, bpa.st has no 1-hour expiry, paste.centos.org needs an API key.)

Final output to David: the litter.catbox.moe URL plus a reminder that it
expires in 1 hour. If the upload fails (non-URL response or curl error),
fall back to printing the full summary in the terminal inside a fenced code
block, and say the upload failed.
