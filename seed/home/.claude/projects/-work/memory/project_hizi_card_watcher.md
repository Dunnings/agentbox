---
name: hizi-card-watcher
description: "@claude mentions on the hizi engine Basecamp card table are handled by a watcher + /hizi-card skill; watcher must be restarted after container reboot"
metadata: 
  node_type: memory
  type: project
  originSessionId: b52cc232-50eb-4afb-b922-a9abd0727b46
---

David's hizi engine Basecamp card table (project 45710420, table 9476253317) is worked via the `hizi-card` skill. A poller at `~/.claude/skills/hizi-card/scripts/watcher.sh` (runs in tmux session `bc-watcher`, started 2026-07-01) watches for comments mentioning `@claude`, acks on the card, and spawns a `card-<id>` tmux session running `claude --dangerously-skip-permissions "/hizi-card <card_url>"`.

Agent comments on Basecamp are posted as David, so they are distinguished by the signature `— Claude (agentbox)` — always include it, and treat comments carrying it as agent-authored. See [[basecamp-cli]].

**Not auto-started:** after a container restart, re-run `tmux new-session -d -s bc-watcher ~/.claude/skills/hizi-card/scripts/watcher.sh` (or wire it into the agentbox entrypoint — not done as of 2026-07-01). State/logs: `~/.local/state/hizi-card-watcher/`.
