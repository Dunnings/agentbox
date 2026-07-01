#!/usr/bin/env bash
# Start the hizi-card Basecamp @claude watcher in a detached tmux session on
# container boot. Idempotent: no-op if the session is already running, or if
# tmux / the skill isn't present. See ~/.claude/skills/hizi-card/SKILL.md.
WATCHER="${HOME:-/home/dev}/.claude/skills/hizi-card/scripts/watcher.sh"
command -v tmux >/dev/null 2>&1 || exit 0
[[ -x "$WATCHER" ]] || exit 0
tmux has-session -t "=bc-watcher" 2>/dev/null && exit 0
tmux new-session -d -s bc-watcher "$WATCHER"
echo "started bc-watcher tmux session"
