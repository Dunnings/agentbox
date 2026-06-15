---
name: mr-reviewer
description: Set David as ASSIGNEE (not reviewer) when opening GitLab MRs in hölle.games repos
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bbb8bd6d-476c-4c33-960d-43cd10d07868
---

Set **David** as the **assignee** — NOT the reviewer — on GitLab MRs in `code.hoelle.games` repos. Do it proactively at MR-creation time (`glab mr create --assignee david.dunnings ...`), and on already-open MRs (`glab mr update <id> --assignee david.dunnings`). Do not pass `--reviewer`.

**Why:** He originally asked to be added as reviewer (2026-05-28, MR !96), but corrected this on 2026-06-10: assignee, not reviewer, on all MRs I make. He reviews and merges from the MR, so assignee is how the work lands on his queue.

**How to apply:** Default to assigning him on every MR I open in a hölle.games repo, unless told otherwise — no need to ask. His GitLab username on `code.hoelle.games` is `david.dunnings` (user id 34). See [[user-david-dunnings]].
