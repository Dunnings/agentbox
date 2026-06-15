---
name: feedback_mr_description_structure
description: Preferred MR/PR description structure — Problem / Fix / Surfacing / Tests headings + review note
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 71ad17e4-89eb-462a-b80e-219ec8998700
---

David likes MR/PR descriptions structured as markdown sections with `##` headings, in this order:

- **Problem** — what was broken and the user-visible symptom (concrete example, e.g. "two coins, 5× + 3×, surfaced as one 8×").
- **Fix** — what changed in the data/code; bullet the new fields/behaviour. Note what stays unchanged for backward compat.
- **Surfacing** (when applicable) — where the change shows up for consumers (UI, AI docs, API).
- **Tests** — what was added + confirmation the suite / typecheck passes.

Close with a short **design note for the reviewer** flagging any judgement call or edge case worth a look (e.g. "position attribution leaves non-divisible remainders ungrouped rather than guessing").

Confirmed good on MR !141 (multipay per-pay breakdown).

**Why:** He reviews and merges async from the MR alone — the description is how he sees the work, so it should lead with the problem and surface trade-offs.

**How to apply:** Use these headings for any non-trivial MR/PR body. Pairs with [[feedback_glab_mr_flags]] (squash + remove-source-branch) and [[feedback_mr_reviewer]] (assign david.dunnings).
