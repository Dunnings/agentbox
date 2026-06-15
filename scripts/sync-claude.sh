#!/usr/bin/env bash
# Sync this container's live Claude memories + custom skills into the repo's
# `seed/home` dir and push them to the current branch, so the personal-branch
# seed stays in lockstep with what Claude actually has.
#
# Run it from inside the agentbox container, from a checkout of your personal
# branch (e.g. a `david` worktree):
#
#   /work/agentbox.worktrees/david/scripts/sync-claude.sh
#
# What it carries (mirrors deletions — removing a memory live removes it here):
#   ~/.claude/projects/-work/memory   → seed/home/.claude/projects/-work/memory
#   ~/.claude/skills                  → seed/home/.claude/skills
#
# It commits and pushes to whatever branch the checkout is on. On another
# server, `git pull` the branch then `./agentbox` — the entrypoint seeds the
# updated files into /home/dev on start.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${HOME:-/home/dev}/.claude"
SEED="${REPO_DIR}/seed/home/.claude"

# Mirror a source dir into the seed: drop the old copy, then recopy so that
# files deleted live (e.g. a memory we removed as wrong) also vanish from seed.
mirror() {
  local src="$1" dst="$2"
  rm -rf "$dst"
  if [[ -d "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp -r "$src" "$dst"
  fi
}

mirror "${SRC}/projects/-work/memory" "${SEED}/projects/-work/memory"
mirror "${SRC}/skills"                "${SEED}/skills"

cd "${REPO_DIR}"
git add seed/home
if git diff --cached --quiet; then
  echo "sync-claude: seed already up to date, nothing to commit"
  exit 0
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
git commit -q -m "chore(seed): sync Claude memories + skills"
git push -q origin "HEAD:${branch}"
echo "sync-claude: committed and pushed to ${branch}"
