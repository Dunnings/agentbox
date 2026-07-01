#!/usr/bin/env bash
# agentbox container entrypoint. Wires up optional credentials, starts the
# control plane, then execs the container CMD (sleep infinity by default).
set -euo pipefail

HOME_DIR="${HOME:-/home/dev}"

# --- VCS credentials via .netrc (HTTPS only) ---------------------------------
# All wiring is opt-in. Set the relevant env vars in .env to enable a host.
umask 077
: > "${HOME_DIR}/.netrc"

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  # x-access-token is GitHub's documented username for PAT-as-password over HTTPS.
  cat >> "${HOME_DIR}/.netrc" <<EOF
machine github.com
login x-access-token
password ${GITHUB_TOKEN}
machine api.github.com
login x-access-token
password ${GITHUB_TOKEN}
EOF
fi

if [[ -n "${GITLAB_TOKEN:-}" && -n "${GITLAB_HOST:-}" ]]; then
  cat >> "${HOME_DIR}/.netrc" <<EOF
machine ${GITLAB_HOST}
login oauth2
password ${GITLAB_TOKEN}
EOF
  mkdir -p "${HOME_DIR}/.config/glab-cli"
  cat > "${HOME_DIR}/.config/glab-cli/config.yml" <<EOF
git_protocol: https
check_update: false
hosts:
  ${GITLAB_HOST}:
    token: ${GITLAB_TOKEN}
    api_protocol: https
    api_host: ${GITLAB_HOST}
    git_protocol: https
EOF
  chmod 600 "${HOME_DIR}/.config/glab-cli/config.yml"
  export GITLAB_HOST GLAB_HOST="${GITLAB_HOST}"
fi
chmod 600 "${HOME_DIR}/.netrc"
umask 022

# --- git identity ------------------------------------------------------------
git config --global user.name  "${GIT_USER_NAME:-agentbox}"
git config --global user.email "${GIT_USER_EMAIL:-agentbox@localhost}"
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global advice.detachedHead false
git config --global --add safe.directory '*'

# --- Seed files into the container (optional) --------------------------------
# Copy everything from an opt-in host directory into /home/dev and/or /work on
# every start. Set SEED_HOME / SEED_WORK in .env to host directories (they get
# bind-mounted read-only); leave them unset to skip. Handy for dropping in
# dotfiles — ~/.npmrc, ~/.gitconfig, SSH known_hosts — or project scaffolding.
# It's a sync-on-run: seeded files overwrite their counterparts, but anything
# not in the seed dir is left untouched. Permissions are preserved (a 600
# .npmrc stays 600) and copies land owned by dev. Hidden files are included.
seed_dir() {
  local src="$1" dst="$2"
  [[ -d "$src" && -n "$(ls -A "$src" 2>/dev/null)" ]] || return 0
  cp -r --preserve=mode,timestamps "$src/." "$dst/"
  echo "seeded ${dst} from ${src}"
}
# Repo-carried seed (always on): files committed under the checkout's
# `seed/home` are bind-mounted here read-only and synced into /home/dev on every
# start. This is how a personal branch (e.g. `david`) carries Claude memories
# and custom skills so a fresh checkout-and-spin-up reproduces them. Applied
# BEFORE the optional host SEED_HOME so a user's SEED_HOME can still override.
seed_dir /etc/agentbox/repo-seed-home "${HOME_DIR}"
seed_dir /etc/agentbox/seed-home "${HOME_DIR}"
seed_dir /etc/agentbox/seed-work  /work

# --- User init hooks (optional) -----------------------------------------------
# Run executable *.sh files under ~/.config/agentbox/init.d after seeding, so
# a seed (or the home volume) can start per-user background services on every
# boot — e.g. a tmux session running a watcher. Hooks run as the container
# user with output collected in /tmp/agentbox-init.log; a failing hook is
# logged but never blocks startup.
if [[ -d "${HOME_DIR}/.config/agentbox/init.d" ]]; then
  for hook in "${HOME_DIR}/.config/agentbox/init.d/"*.sh; do
    [[ -x "$hook" ]] || continue
    echo "[$(date -Is)] running init hook ${hook}" >> /tmp/agentbox-init.log
    "$hook" >> /tmp/agentbox-init.log 2>&1 \
      || { rc=$?; echo "[$(date -Is)] init hook ${hook} exited ${rc}" >> /tmp/agentbox-init.log; }
  done
fi

# --- Claude Code context (only used if you actually run Claude Code) ---------
# Symlink the image's CLAUDE.md into the home volume so rebuilds always pick up
# edits. Replaces an existing symlink but won't overwrite a real file — if the
# user wrote their own ~/.claude/CLAUDE.md, leave it alone.
mkdir -p "${HOME_DIR}/.claude"
if [[ ! -e "${HOME_DIR}/.claude/CLAUDE.md" || -L "${HOME_DIR}/.claude/CLAUDE.md" ]]; then
  ln -sfn /etc/agentbox/CLAUDE.md "${HOME_DIR}/.claude/CLAUDE.md"
fi

# --- npm private-registry auth (optional) -----------------------------------
# Set NPM_REGISTRY (full URL) + NPM_TOKEN to authenticate against a private
# registry. Optionally set NPM_SCOPE (e.g. @myorg) to point just that scope at
# the registry; without a scope it becomes the default registry for all
# installs. Writes ~/.npmrc with an _authToken keyed to the registry host/path.
if [[ -n "${NPM_REGISTRY:-}" && -n "${NPM_TOKEN:-}" ]]; then
  umask 077
  # npm keys _authToken by registry minus scheme, with a trailing slash:
  #   //host[/path]/:_authToken=...
  npm_reg_key="${NPM_REGISTRY#*://}"
  npm_reg_key="${npm_reg_key%/}/"
  {
    if [[ -n "${NPM_SCOPE:-}" ]]; then
      echo "${NPM_SCOPE}:registry=${NPM_REGISTRY}"
    else
      echo "registry=${NPM_REGISTRY}"
    fi
    echo "//${npm_reg_key}:_authToken=${NPM_TOKEN}"
  } > "${HOME_DIR}/.npmrc"
  chmod 600 "${HOME_DIR}/.npmrc"
  umask 022
fi
mkdir -p "${HOME_DIR}/.npm"

# --- Control plane -----------------------------------------------------------
# Background the FastAPI app on :9119. tini reaps it; the supervising loop
# restarts it if it crashes so a single bad request doesn't take it offline
# until the container restarts (which would also wipe /tmp tmux state).
if [[ -x /opt/controlplane-venv/bin/python && -f /opt/controlplane/server.py ]]; then
  (
    while true; do
      # || capture keeps the inherited `set -e` from killing the supervisor
      # subshell on a nonzero exit — which would silently disable restarts.
      /opt/controlplane-venv/bin/python /opt/controlplane/server.py \
        >> /tmp/controlplane.log 2>&1 && rc=0 || rc=$?
      echo "[$(date -Is)] controlplane exited ${rc}, restarting in 5s" \
        >> /tmp/controlplane.log
      sleep 5
    done
  ) &
fi

exec "$@"
