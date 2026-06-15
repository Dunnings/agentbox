---
name: feedback_persist_memories_to_agentbox
description: "After creating/updating/deleting any memory or custom skill, sync it to the agentbox `david` branch so it survives container recreation"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 71ad17e4-89eb-462a-b80e-219ec8998700
---

This container is spun up from the **agentbox** repo (github.com/Dunnings/agentbox). Memories live in the `home` Docker volume, which is lost when the container is recreated on another server. The `david` branch carries them in `seed/home/.claude/` and the entrypoint seeds them into `/home/dev` on every start.

**Whenever I create, update, or delete a memory file (or a custom skill under `~/.claude/skills/`), I must also push it to the `david` branch** — otherwise the change is invisible on any other server and is lost on container recreation.

How: run the sync script from the agentbox `david` checkout inside the container:

```
/work/agentbox.worktrees/david/scripts/sync-claude.sh
```

(If that worktree doesn't exist yet: `cd /work/agentbox && git fetch origin && git worktree add ../agentbox.worktrees/david david`. The script path is wherever the `david` branch is checked out.) It mirrors `~/.claude` memories + skills into `seed/home`, commits, and pushes to `david`.

**Why:** Without this, persistent memory only persists on this one host; the whole point of the `david` branch is cross-server reproducibility.

**How to apply:** Treat the sync push as part of finishing any task that touched memory/skills, the same way [[feedback_fold_into_open_mr]] treats the MR as part of finishing a code task. Don't ask first — just sync. Related: [[feedback_mr_description_structure]], [[feedback_glab_mr_flags]].
