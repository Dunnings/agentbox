---
name: feedback_glab_mr_flags
description: "When creating GitLab MRs with glab, enable Delete source branch + Squash commits"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 57203ccc-d4f1-429f-a050-e45823800a19
---

When creating an MR with `glab mr create`, always enable both "Delete source branch" and "Squash commits".

**Why:** Keeps the repo tidy — no lingering merged feature branches, and each MR lands as a single squashed commit on main.

**How to apply:** Pass `--remove-source-branch --squash-before-merge` to `glab mr create` (alongside the usual `--yes`/`--fill`/`--reviewer david.dunnings`). See [[feedback_mr_reviewer]].
