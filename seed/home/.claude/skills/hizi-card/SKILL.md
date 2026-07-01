---
name: hizi-card
description: >
  Pick a card from the hizi engine Basecamp card table and work it end-to-end:
  implement the request/bugfix and open a GitLab MR (linked on the card), or ask
  for clarification on the card if the request is underspecified. Use when the
  user says "work on a basecamp card", "pick a card", "check the card table",
  or names a specific hizi card/URL to work on.
---

# /hizi-card — work a card from the hizi engine card table

Work exactly **one card per invocation** from the hizi engine card table, end to end.

- Account: `4718627` (Hölle Games) — already the CLI default
- Project: `45710420` (hizi engine)
- Card table: `9476253317`
- CLI binary: `~/.local/bin/basecamp` (NOT on non-interactive PATH — always use the full path; alias `B=~/.local/bin/basecamp` at the start)

Column IDs (verify with `cards columns` if a move fails; they may drift):

| Column | ID | Meaning |
|---|---|---|
| Triage | `9476253319` | new, unworked requests |
| Not now | `9476253321` | deferred — never touch |
| Figuring it out | `9476253322` | blocked on clarification (usually a question we asked) |
| In progress | `9476253323` | actively being worked |
| Pending review | `9855747504` | MR open, awaiting review |
| Done | `9476253325` | shipped — never touch |

## Agent comment signature

Comments are posted under David's own account, so authorship cannot distinguish
the agent from the human. **Every comment this skill posts MUST end with:**

```
<em>— Claude (agentbox)</em>
```

and every run MUST use that marker to classify existing comments: a comment
containing `— Claude (agentbox)` is ours; anything else is a human reply.

## Step 1 — pick a card

If the user gave a card URL or ID as arguments, use that card (parse URLs with
`$B url parse "<url>" --json`) and skip selection. Otherwise select, in priority order:

1. **Answered clarification** — cards in *Figuring it out* whose **latest** comment
   is NOT ours (a human replied since we asked). Fetch candidates:
   `$B cards list --column 9476253322 --card-table 9476253317 --in 45710420 --json`,
   then `$B comments list <card_id> --in 45710420 --json` per card and check the
   last comment for the signature marker.
2. **Triage, top first** — `$B cards list --column 9476253319 --card-table 9476253317 --in 45710420 --json`.
   Position in the column is priority; take the first card you can act on.

Never pick from *Not now*, *In progress*, *Pending review*, or *Done*. If a card
already has an MR URL in our comments, it is not a candidate (it's mid-review even
if it sits elsewhere). If no candidate exists, report "no workable cards" and stop —
do not invent work.

## Step 2 — understand the card fully (before judging feasibility)

```bash
$B cards show <card_id> --in 45710420 --download-attachments --json
$B comments list <card_id> --in 45710420 --json
```

- **View every downloaded attachment with the Read tool** — screenshots and
  mockups often carry the real spec; treat them as part of the card text.
- Read the full comment thread. On a resumed card the human's latest reply is
  the missing information you previously asked for.
- Identify the target repo. The hizi group on GitLab (`code.hoelle.games/hizi/...`)
  contains: `hizi-engine` (the engine core; most `[BUG]`/`[FR]` cards land here),
  `hizi-engine-creator` (the engine.hizi.io web app), `hizi-engine-sdk`,
  `hizi-engine-tester`, `hizi-engine-generator-ts`, `hizi-engine-generator-py`,
  `docs`, `game-studio-api`. Clones live at `/work/hizi/<repo>` (some also at
  `/work/<repo>` — reuse whatever exists; clone into `/work/hizi/` only if absent).
  Confirm the guess by grepping the repo for terms from the card (feature names,
  error strings, UI copy) before committing to it.

## Step 3 — decide: implement or ask

Implement only if you can state all of these from the card + thread + code:
**what** should change, **where** (repo + subsystem located in code), **expected
behaviour** (for bugs: reproduce or at least pinpoint the fault in code), and
**how you'll verify it**. Ambiguity about *design intent* (product behaviour,
weighting semantics, UX) is a blocker — ask. Ambiguity you can resolve by
reading code is not — go read the code.

### Not enough info → ask on the card

1. Post ONE comment with the specific questions (numbered if several), each
   showing you did the homework — quote the code path or behaviour you found and
   state what decision you need. Markdown works; end with the signature marker:
   ```bash
   $B comment <card_id> "..." --in 45710420 --json
   ```
2. Move the card: `$B cards move <card_id> --to 9476253322 --in 45710420 --json`
3. Report to the user: which card, what you asked, link to the card. Stop.

### Enough info → implement

1. Move the card to In progress: `$B cards move <card_id> --to 9476253323 --in 45710420 --json`
2. Branch in a worktree off the up-to-date default branch (main checkout stays clean):
   ```bash
   cd /work/hizi/<repo> && git fetch origin
   git worktree add ../<repo>.worktrees/<branch> -b <branch> origin/<default-branch>
   ```
   Branch name: `card-<card_id>-<short-slug>`.
3. Implement. Match existing code style; add/adjust tests; run the repo's test
   suite (and lint/typecheck if configured) and make it pass.
4. Commit and push (`git push -u origin <branch>`).
5. Open the MR (per standing MR conventions):
   ```bash
   glab mr create --assignee david.dunnings --remove-source-branch --squash-before-merge \
     --title "..." --description "..."
   ```
   Description sections: `## Problem` / `## Fix` / `## Surfacing` / `## Tests`,
   plus a short reviewer design note. Reference the card URL in the description.
   Use `--draft` if anything is unverified or you had to make a judgment call.
6. Comment on the card: 2–3 sentences on what was done + the MR URL + signature
   marker. Then move the card to Pending review:
   `$B cards move <card_id> --to 9855747504 --in 45710420 --json`
7. Report to the user: card title, what you implemented, MR URL, card URL.

## Guardrails

- One card per run. Finish (MR opened or question posted) before ending the turn.
- Never move cards out of *Not now* or *Done*; never grab cards a human may be
  working (*In progress* without our marker).
- If mid-implementation you hit a genuine design question, don't guess: push what
  exists, open a **draft** MR, ask the question on the card (with signature),
  move the card back to *Figuring it out*, and say so in your report.
- If a `cards move` or comment fails, report it — don't leave the board silently
  out of sync with reality.
- Judgment calls that didn't block you (naming, edge-case behaviour) go in the
  MR's reviewer note, not as card questions.
