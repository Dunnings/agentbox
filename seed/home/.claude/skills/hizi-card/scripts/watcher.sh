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

STATE_DIR=~/.local/state/hizi-card-watcher
PROCESSED="$STATE_DIR/processed-ids"
HWM_FILE="$STATE_DIR/high-water-mark"
LOG="$STATE_DIR/watcher.log"

mkdir -p "$STATE_DIR"
touch "$PROCESSED"

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

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
                 parent_type: .parent.type}] | sort_by(.created_at)')" || batch='[]'
  [[ -z "$batch" ]] && batch='[]'

  while IFS= read -r c; do
    [[ -z "$c" ]] && continue
    id=$(jq -r '.id' <<<"$c")
    created=$(jq -r '.created_at' <<<"$c")
    card_id=$(jq -r '.card_id' <<<"$c")
    card_title=$(jq -r '.card_title' <<<"$c")
    ptype=$(jq -r '.parent_type' <<<"$c")

    # Advance the mark for every comment we've looked at, matched or not.
    [[ "$created" > "$(cat "$HWM_FILE")" ]] && printf '%s\n' "$created" > "$HWM_FILE"
    grep -qx "$id" "$PROCESSED" && continue
    printf '%s\n' "$id" >> "$PROCESSED"

    [[ "$ptype" == Kanban::* ]] || continue

    content="$("$BC" show comment "$id" --in "$PROJECT" --jq '.data.content' 2>>"$LOG")"
    # Trigger: mentions @claude, and isn't one of our own signed comments.
    grep -qi '@claude' <<<"$content" || continue
    grep -qF "$SIGNATURE" <<<"$content" && continue

    card_url="https://3.basecamp.com/$ACCOUNT/buckets/$PROJECT/card_tables/cards/$card_id"
    session="card-$card_id"

    if tmux has-session -t "=$session" 2>/dev/null; then
      log "mention on card $card_id ($card_title) but session $session already running — acking only"
      "$BC" comment "$card_id" \
        "Already on this one — a session is running for this card (tmux: \`$session\`). <em>$SIGNATURE</em>" \
        --in "$PROJECT" --json >/dev/null 2>>"$LOG"
      continue
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
