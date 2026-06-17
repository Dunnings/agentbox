# agentbox: a sandboxed Linux container with a browser-based tmux control plane.
# Defense-in-depth — non-root user, all capabilities dropped at runtime, no host
# bind mounts, resource caps. Treat any token mounted into the container as the
# actual security boundary and scope it tightly.

FROM debian:12-slim

ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
ARG NODE_MAJOR=22
ARG GLAB_VERSION=1.92.1

# --- Optional toolchains (1 = install, 0 = skip) -----------------------------
# SOURCE OF TRUTH IS .env, NOT THIS FILE. The normal path is `./agentbox`, where
# docker-compose.yml reads .env and forwards each flag here as a build arg
# (see its `build.args` block). A Dockerfile can't read .env itself, so these
# ARG lines exist to (1) declare the build args — an undeclared --build-arg is
# ignored — and (2) provide a fallback default ONLY for a bare `docker build`
# with no compose. Edit values in .env; the defaults below just keep a
# standalone build sensible (standard tools on, extras/AI agents off).
#
# Standard toolchains — ON by default. Flip to 0 in .env to slim the image.
# (Claude Code needs Node, so INSTALL_CLAUDE is a no-op unless INSTALL_NODE=1.)
ARG INSTALL_NODE=1
ARG INSTALL_BUN=1
ARG INSTALL_RUST=1
ARG INSTALL_DOCKER=1
ARG INSTALL_GH=1
ARG INSTALL_GLAB=1
ARG INSTALL_CLAUDE=1
# Playwright (headless Chromium + system libs) — also needs INSTALL_NODE=1.
ARG INSTALL_PLAYWRIGHT=1
#
# Extra languages & utilities — OFF by default (opt in by setting to 1 in .env).
# INSTALL_PYTHON adds dev tooling (pip + pipx + uv); the python3 interpreter
# itself is always present because the control plane uses it.
ARG INSTALL_PYTHON=0
ARG INSTALL_GO=0
ARG INSTALL_DENO=0
ARG INSTALL_RUBY=0
ARG INSTALL_SEARCH=0
ARG INSTALL_YQ=0
ARG INSTALL_SHELLCHECK=0
ARG INSTALL_DB_CLIENTS=0
ARG GO_VERSION=1.23.4
ARG YQ_VERSION=4.44.3
ARG PLAYWRIGHT_VERSION=1.49.1
#
# CLI AI coding agents — OFF by default (opt in by setting to 1 in .env).
# Copilot/Codex/Gemini/opencode install via npm (need INSTALL_NODE=1); Aider
# installs via pipx (needs INSTALL_PYTHON=1). Claude Code is in the standard
# set above.
ARG INSTALL_COPILOT=0
ARG INSTALL_CODEX=0
ARG INSTALL_GEMINI=0
ARG INSTALL_OPENCODE=0
ARG INSTALL_AIDER=0

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# --- Base packages -----------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget gnupg git \
        build-essential pkg-config libssl-dev \
        unzip xz-utils procps less jq vim-tiny tini tmux \
        openssh-client iproute2 \
        python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

# --- Control-plane Python venv (FastAPI + uvicorn) ---------------------------
# Lives in /opt so it's outside the persistent /home volume — survives volume
# wipes. Read-only at runtime; non-root users can execute the interpreter.
RUN python3 -m venv /opt/controlplane-venv \
    && /opt/controlplane-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/controlplane-venv/bin/pip install --no-cache-dir \
        fastapi uvicorn[standard] python-multipart

# --- Node.js (for Claude Code and general TS/JS work) ------------------------
RUN if [ "$INSTALL_NODE" = "1" ]; then \
        curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
        && apt-get install -y --no-install-recommends nodejs \
        && rm -rf /var/lib/apt/lists/* \
        && npm config set fund false \
        && npm config set update-notifier false ; \
    else echo "INSTALL_NODE=0 — skipping Node.js"; fi

# --- glab (pinned — bump GLAB_VERSION build-arg to update) -------------------
RUN if [ "$INSTALL_GLAB" = "1" ]; then \
        ARCH="$(dpkg --print-architecture)" \
        && curl -fsSL "https://gitlab.com/gitlab-org/cli/-/releases/v${GLAB_VERSION}/downloads/glab_${GLAB_VERSION}_linux_${ARCH}.deb" \
             -o /tmp/glab.deb \
        && apt-get update && apt-get install -y --no-install-recommends /tmp/glab.deb \
        && rm -rf /var/lib/apt/lists/* /tmp/glab.deb ; \
    else echo "INSTALL_GLAB=0 — skipping glab"; fi

# --- gh (GitHub CLI, from the official cli.github.com apt repo) --------------
# Auth is taken from $GITHUB_TOKEN at runtime — no `gh auth login` needed.
RUN if [ "$INSTALL_GH" = "1" ]; then \
        install -dm 0755 /etc/apt/keyrings \
        && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
             -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
        && chmod 0644 /etc/apt/keyrings/githubcli-archive-keyring.gpg \
        && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
             > /etc/apt/sources.list.d/github-cli.list \
        && apt-get update && apt-get install -y --no-install-recommends gh \
        && rm -rf /var/lib/apt/lists/* ; \
    else echo "INSTALL_GH=0 — skipping GitHub CLI"; fi

# --- Docker CLI + compose/buildx plugins (no daemon in this image) -----------
# The daemon runs in the sidecar `dind` service; agentbox only needs the
# client. DOCKER_HOST=tcp://dind:2375 is set in docker-compose.yml, so
# `docker` / `docker compose` / `docker buildx` here talk to the sidecar over
# the private compose network — not to anything on the host.
RUN if [ "$INSTALL_DOCKER" = "1" ]; then \
        install -dm 0755 /etc/apt/keyrings \
        && curl -fsSL https://download.docker.com/linux/debian/gpg \
             -o /etc/apt/keyrings/docker.asc \
        && chmod 0644 /etc/apt/keyrings/docker.asc \
        && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" \
             > /etc/apt/sources.list.d/docker.list \
        && apt-get update && apt-get install -y --no-install-recommends \
             docker-ce-cli docker-compose-plugin docker-buildx-plugin \
        && rm -rf /var/lib/apt/lists/* ; \
    else echo "INSTALL_DOCKER=0 — skipping Docker CLI"; fi

# --- Bun (system-wide so /home/dev can be a fresh volume) --------------------
RUN if [ "$INSTALL_BUN" = "1" ]; then \
        curl -fsSL https://bun.sh/install | BUN_INSTALL=/usr/local bash \
        && ln -sf /usr/local/bin/bun /usr/local/bin/bunx ; \
    else echo "INSTALL_BUN=0 — skipping Bun"; fi

# --- Rust (system-wide via CARGO_HOME/RUSTUP_HOME in /usr/local) -------------
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:/usr/local/bin:${PATH}
RUN if [ "$INSTALL_RUST" = "1" ]; then \
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --default-toolchain stable --profile minimal --no-modify-path \
        && chmod -R a+rwX "${RUSTUP_HOME}" "${CARGO_HOME}" ; \
    else echo "INSTALL_RUST=0 — skipping Rust"; fi

# === Extra languages & utilities (opt-in) ====================================

# --- Python dev tooling (pip + pipx + uv) ------------------------------------
# python3 itself is always installed (the control plane needs it). Debian's
# system pip is PEP 668 "externally managed", so we add pipx + uv — the
# correct way to install apps / manage environments — alongside pip for venvs.
RUN if [ "$INSTALL_PYTHON" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends python3-pip pipx \
        && rm -rf /var/lib/apt/lists/* \
        && curl -LsSf https://astral.sh/uv/install.sh \
           | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh ; \
    else echo "INSTALL_PYTHON=0 — skipping Python dev tooling"; fi

# --- Go (official tarball, pinned — bump GO_VERSION to update) ---------------
ENV PATH=/usr/local/go/bin:${PATH}
RUN if [ "$INSTALL_GO" = "1" ]; then \
        ARCH="$(dpkg --print-architecture)" \
        && curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" -o /tmp/go.tgz \
        && tar -C /usr/local -xzf /tmp/go.tgz \
        && rm /tmp/go.tgz ; \
    else echo "INSTALL_GO=0 — skipping Go"; fi

# --- Deno (system-wide) ------------------------------------------------------
RUN if [ "$INSTALL_DENO" = "1" ]; then \
        curl -fsSL https://deno.land/install.sh \
           | DENO_INSTALL=/usr/local sh -s -- -y ; \
    else echo "INSTALL_DENO=0 — skipping Deno"; fi

# --- Ruby (+ bundler) --------------------------------------------------------
RUN if [ "$INSTALL_RUBY" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends ruby ruby-dev \
        && rm -rf /var/lib/apt/lists/* \
        && gem install --no-document bundler ; \
    else echo "INSTALL_RUBY=0 — skipping Ruby"; fi

# --- Search utilities: ripgrep (rg), fd, fzf ---------------------------------
RUN if [ "$INSTALL_SEARCH" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends ripgrep fd-find fzf \
        && rm -rf /var/lib/apt/lists/* \
        && ln -sf "$(command -v fdfind)" /usr/local/bin/fd ; \
    else echo "INSTALL_SEARCH=0 — skipping ripgrep/fd/fzf"; fi

# --- yq (mikefarah, single binary — bump YQ_VERSION to update) ---------------
RUN if [ "$INSTALL_YQ" = "1" ]; then \
        ARCH="$(dpkg --print-architecture)" \
        && curl -fsSL "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${ARCH}" \
             -o /usr/local/bin/yq \
        && chmod 0755 /usr/local/bin/yq ; \
    else echo "INSTALL_YQ=0 — skipping yq"; fi

# --- shellcheck --------------------------------------------------------------
RUN if [ "$INSTALL_SHELLCHECK" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends shellcheck \
        && rm -rf /var/lib/apt/lists/* ; \
    else echo "INSTALL_SHELLCHECK=0 — skipping shellcheck"; fi

# --- Database clients: psql, sqlite3, redis-cli ------------------------------
RUN if [ "$INSTALL_DB_CLIENTS" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
             postgresql-client redis-tools sqlite3 \
        && rm -rf /var/lib/apt/lists/* ; \
    else echo "INSTALL_DB_CLIENTS=0 — skipping database clients"; fi

# --- Playwright (headless Chromium + the system libraries it needs) ----------
# Browser end-to-end testing / screenshotting. The hard part in a slim image is
# the browser's shared libraries (libnss3, libgbm1, …), which need root to apt-
# install — so we bake them in here. Chromium itself is installed into a shared,
# world-writable PLAYWRIGHT_BROWSERS_PATH (the convention the official
# Playwright images use) so any project's `playwright` finds it with no
# per-project download and no root. Needs Node (npx) + network at build time.
# Bump PLAYWRIGHT_VERSION to match the Playwright npm version your projects use.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p /ms-playwright && chmod -R a+rwX /ms-playwright \
    && if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then \
        if command -v npx >/dev/null 2>&1; then \
            npx --yes playwright@${PLAYWRIGHT_VERSION} install --with-deps chromium \
            && chmod -R a+rwX /ms-playwright \
            && rm -rf /var/lib/apt/lists/* ; \
        else echo "WARN: INSTALL_PLAYWRIGHT=1 but Node is missing (INSTALL_NODE=0) — skipping Playwright"; fi ; \
    else echo "INSTALL_PLAYWRIGHT=0 — skipping Playwright"; fi

# === CLI AI coding agents (opt-in) ===========================================
# npm-based agents (Copilot, Codex, Gemini) need Node; Aider needs pipx (the
# Python option). Each skips with a warning if its prerequisite is missing
# rather than failing the build.

# --- GitHub Copilot CLI ------------------------------------------------------
RUN if [ "$INSTALL_COPILOT" = "1" ]; then \
        if command -v npm >/dev/null 2>&1; then npm install -g @github/copilot ; \
        else echo "WARN: INSTALL_COPILOT=1 but Node is missing (INSTALL_NODE=0) — skipping"; fi ; \
    else echo "INSTALL_COPILOT=0 — skipping GitHub Copilot CLI"; fi

# --- OpenAI Codex CLI --------------------------------------------------------
RUN if [ "$INSTALL_CODEX" = "1" ]; then \
        if command -v npm >/dev/null 2>&1; then npm install -g @openai/codex ; \
        else echo "WARN: INSTALL_CODEX=1 but Node is missing (INSTALL_NODE=0) — skipping"; fi ; \
    else echo "INSTALL_CODEX=0 — skipping OpenAI Codex CLI"; fi

# --- Google Gemini CLI -------------------------------------------------------
RUN if [ "$INSTALL_GEMINI" = "1" ]; then \
        if command -v npm >/dev/null 2>&1; then npm install -g @google/gemini-cli ; \
        else echo "WARN: INSTALL_GEMINI=1 but Node is missing (INSTALL_NODE=0) — skipping"; fi ; \
    else echo "INSTALL_GEMINI=0 — skipping Google Gemini CLI"; fi

# --- opencode (via npm) ------------------------------------------------------
RUN if [ "$INSTALL_OPENCODE" = "1" ]; then \
        if command -v npm >/dev/null 2>&1; then npm install -g opencode-ai ; \
        else echo "WARN: INSTALL_OPENCODE=1 but Node is missing (INSTALL_NODE=0) — skipping"; fi ; \
    else echo "INSTALL_OPENCODE=0 — skipping opencode"; fi

# --- Aider (via pipx) --------------------------------------------------------
RUN if [ "$INSTALL_AIDER" = "1" ]; then \
        if command -v pipx >/dev/null 2>&1; then \
            PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install aider-chat ; \
        else echo "WARN: INSTALL_AIDER=1 but pipx is missing (INSTALL_PYTHON=0) — skipping"; fi ; \
    else echo "INSTALL_AIDER=0 — skipping Aider"; fi

# --- Claude Code CLI (global npm install, runs as any user) ------------------
# Always installs the latest published version. CLAUDE_VERSION acts as a
# cache-buster — change its value (sandbox.sh passes a daily date) to force this
# layer to rebuild. Kept last so busting it doesn't invalidate Rust/Bun/glab.
ARG CLAUDE_VERSION=latest
RUN if [ "$INSTALL_CLAUDE" = "1" ]; then \
        echo "claude-code cache-bust: ${CLAUDE_VERSION}" ; \
        if command -v npm >/dev/null 2>&1; then \
            npm install -g @anthropic-ai/claude-code ; \
        else \
            echo "WARN: INSTALL_CLAUDE=1 but Node is missing (INSTALL_NODE=0) — skipping Claude Code"; \
        fi ; \
    else echo "INSTALL_CLAUDE=0 — skipping Claude Code"; fi

# --- Non-root user -----------------------------------------------------------
RUN groupadd -g "${USER_GID}" "${USERNAME}" \
    && useradd -m -s /bin/bash -u "${USER_UID}" -g "${USER_GID}" "${USERNAME}" \
    && mkdir -p /work \
    && chown "${USERNAME}:${USERNAME}" /work

# --- tmux defaults -----------------------------------------------------------
# Mouse on so wheel-up enters copy-mode and scrolls the pane buffer (the web
# terminal can't use xterm.js scrollback because tmux runs in alt-screen).
# History bumped well above the 2000-line default so a long Claude session
# stays scrollable. window-size latest: when several browser tabs attach to one
# session, size the window to the most-recently-active client instead of the
# smallest, so a phone tab no longer squeezes a desktop tab.
RUN printf '%s\n' \
        'set -g mouse on' \
        'set -g history-limit 50000' \
        'set -g set-clipboard on' \
        "set -as terminal-features 'xterm*:clipboard'" \
        'set -g window-size latest' \
        'set -g status off' \
    > /etc/tmux.conf

# --- Control plane app (changes most often — kept late to preserve cache) ----
COPY controlplane /opt/controlplane

# --- Entrypoint --------------------------------------------------------------
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY CLAUDE.md /etc/agentbox/CLAUDE.md
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
    && chmod 0644 /etc/agentbox/CLAUDE.md

USER ${USERNAME}
WORKDIR /work

# Persist bash history + useful defaults inside the home volume
RUN printf '%s\n' \
        'export HISTFILE=$HOME/.bash_history' \
        'export HISTSIZE=10000' \
        'export HISTFILESIZE=20000' \
        'shopt -s histappend' \
        'export PS1="\[\e[36m\]agentbox\[\e[0m\]:\w\$ "' \
        'export PATH=$HOME/.local/bin:$PATH' \
    >> /home/dev/.bashrc

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
