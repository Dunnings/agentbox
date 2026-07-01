#!/usr/bin/env bash
# hizi-card watcher — poll the hizi engine Basecamp card table for new comments
# that mention @claude, ack on the card, and spawn a detached tmux session
# running Claude Code with /hizi-card pointed at that card.
#
# Start it (survives until the container stops):
#   tmux new-session -d -s bc-watcher ~/.claude/skills/hizi-card/scripts/watcher.sh
#
# Watch it:      tmux attach -t bc-watcher      (Ctrl-b d to detach)
# Worker runs:   tmux attach -t card-<card_id>
# Logs + state:  ~/.local/state/hizi-card-watcher/
#
# Basecamp webhooks can't reach this container (no public inbound URL), hence
# polling. Comments are fetched project-wide; in this project the only cards
# are on the watched table, so no per-card table check is done.
set -uo pipefail

BC=~/.local/bin/basecamp
PROJECT=45710420
ACCOUNT=4718627
POLL_INTERVAL="${POLL_INTERVAL:-60}"
SIGNATURE='— Claude (agentbox)'
# Only this Basecamp person may trigger runs (David's per-account person ID —
# NOT the launchpad identity ID). Mentions by anyone else are logged + ignored.
ALLOWED_CREATOR=31104867

STATE_DIR=~/.local/state/hizi-card-watcher
PROCESSED="$STATE_DIR/processed-ids"
HWM_FILE="$STATE_DIR/high-water-mark"
LOG="$STATE_DIR/watcher.log"

mkdir -p "$STATE_DIR"
touch "$PROCESSED"

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

# Is a claude process still alive in this tmux session? Sessions are spawned
# via `bash -c "... claude ...; exec bash"`, so claude is a child of the pane
# process while running, and the pane degrades to a bare bash once it exits.
claude_alive() {
  # NB: display-message/send-keys target panes and do NOT accept tmux's "="
  # exact-match prefix (only session-scoped commands like has-session do).
  # Session names are distinct equal-length card-<id> strings, so a plain
  # name can't prefix-collide here.
  local pane_pid
  pane_pid="$(tmux display-message -p -t "$1" '#{pane_pid}' 2>/dev/null)" || return 1
  [[ -n "$pane_pid" ]] || return 1
  [[ "$(ps -o comm= -p "$pane_pid" 2>/dev/null)" == claude ]] && return 0
  pgrep -P "$pane_pid" -x claude >/dev/null 2>&1
}

# First run: start from "now" so we never chew through history.
if [[ ! -s "$HWM_FILE" ]]; then
  date -u +%FT%T.000Z > "$HWM_FILE"
  log "initialized high-water mark to $(cat "$HWM_FILE")"
fi

log "watcher started (project=$PROJECT, interval=${POLL_INTERVAL}s)"

while true; do
  hwm="$(cat "$HWM_FILE")"

  batch="$("$BC" recordings comments --in "$PROJECT" \
            --sort created_at --direction desc --limit 50 --json 2>>"$LOG" |
          jq -c --arg hwm "$hwm" \
            '[.data[]? | select(.created_at > $hwm)
              | {id, created_at, card_id: .parent.id, card_title: .parent.title,
                 parent_type: .parent.type, creator_id: .creator.id,
                 creator_name: .creator.name}] | sort_by(.created_at)')" || batch='[]'
  [[ -z "$batch" ]] && batch='[]'

  while IFS= read -r c; do
    [[ -z "$c" ]] && continue
    id=$(jq -r '.id' <<<"$c")
    created=$(jq -r '.created_at' <<<"$c")
    card_id=$(jq -r '.card_id' <<<"$c")
    card_title=$(jq -r '.card_title' <<<"$c")
    ptype=$(jq -r '.parent_type' <<<"$c")
    creator_id=$(jq -r '.creator_id' <<<"$c")
    creator_name=$(jq -r '.creator_name' <<<"$c")

    # Advance the mark for every comment we've looked at, matched or not.
    [[ "$created" > "$(cat "$HWM_FILE")" ]] && printf '%s\n' "$created" > "$HWM_FILE"
    grep -qx "$id" "$PROCESSED" && continue
    printf '%s\n' "$id" >> "$PROCESSED"

    [[ "$ptype" == Kanban::* ]] || continue

    content="$("$BC" show comment "$id" --in "$PROJECT" --jq '.data.content' 2>>"$LOG")"
    # Trigger: mentions @claude, and isn't one of our own signed comments.
    grep -qi '@claude' <<<"$content" || continue
    grep -qF "$SIGNATURE" <<<"$content" && continue

    # Authorization: only David's mentions trigger a run. Others are logged
    # only — no reply on the card, and their comment text is never fed to a
    # session as an instruction.
    if [[ "$creator_id" != "$ALLOWED_CREATOR" ]]; then
      log "ignored @claude mention by non-allowed user ${creator_name} (${creator_id}) on card $card_id ($card_title)"
      continue
    fi

    card_url="https://3.basecamp.com/$ACCOUNT/buckets/$PROJECT/card_tables/cards/$card_id"
    session="card-$card_id"

    if tmux has-session -t "=$session" 2>/dev/null; then
      if claude_alive "$session"; then
        # Forward the mention into the live session — it keeps its context.
        # If claude is mid-turn the injected text queues as a steering message.
        log "forwarding comment $id on card $card_id to live session $session"
        "$BC" comment "$card_id" \
          "Got it — picking this up in the same session (tmux: \`$session\`). <em>$SIGNATURE</em>" \
          --in "$PROJECT" --json >/dev/null 2>>"$LOG" \
          || log "WARNING: forward-ack comment on card $card_id failed"
        tmux send-keys -t "$session" -l "David posted a new @claude comment on the Basecamp card you are working (card $card_id). Fetch the latest comments on the card and continue the task — if you were waiting on clarification, it should now be answered. Finish per the skill's completion steps (implement + MR + comment + move card, or ask again if still blocked)."
        tmux send-keys -t "$session" Enter
        continue
      fi
      log "session $session exists but claude is gone — replacing with a fresh session"
      tmux kill-session -t "=$session" 2>/dev/null || true
    fi

    log "trigger: comment $id on card $card_id ($card_title) — spawning $session"
    "$BC" comment "$card_id" \
      "On it 👀 — I've picked this card up and I'm assessing whether there's enough here to implement. I'll follow up shortly with either a \"working on it\" + MR, or the questions I need answered. (tmux: \`$session\`) <em>$SIGNATURE</em>" \
      --in "$PROJECT" --json >/dev/null 2>>"$LOG" \
      || log "WARNING: ack comment on card $card_id failed"

    tmux new-session -d -s "$session" \
      "cd /work && claude --dangerously-skip-permissions '/hizi-card $card_url (triggered by an @claude mention on the card — work this specific card)'; exec bash" \
      || log "ERROR: failed to spawn tmux session $session"
  done < <(jq -c '.[]' <<<"$batch")

  # Keep the processed-ids file from growing forever.
  if [[ $(wc -l < "$PROCESSED") -gt 1000 ]]; then
    tail -n 500 "$PROCESSED" > "$PROCESSED.tmp" && mv "$PROCESSED.tmp" "$PROCESSED"
  fi

  sleep "$POLL_INTERVAL"
done
