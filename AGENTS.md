# Adding a new tool to agentbox

This document covers the full checklist for adding a new opt-in CLI tool (language
runtime, utility, or AI coding agent). Every step is required — missing any one of
them has caused bugs before.

---

## 0. Verify the package name first

Before writing a line of code, confirm the exact package name on the relevant
registry. The binary name and the package name often differ.

```sh
# npm — check the package page or search:
npm info <package-name>

# pipx / PyPI:
pip index versions <package-name>

# GitHub releases (for binary-only tools):
gh release list --repo <owner>/<repo>
```

Common trap: the obvious name (`opencode`) may be taken by an unrelated package.
Always run the install command in a throwaway environment before wiring it into
the Dockerfile.

---

## 1. Dockerfile — `image/Dockerfile`

### 1a. Declare the build arg

Add `ARG INSTALL_<TOOL>=0` in the correct block near the top of the file.
There are two distinct blocks — put the new arg in the right one:

- **Standard toolchains** (on by default, users opt *out*): languages, Docker,
  GH/GitLab CLIs, Claude Code, Playwright.
- **Extra languages & utilities** (off by default, users opt *in*): Python dev
  tooling, Go, Deno, Ruby, search utils, yq, shellcheck, DB clients.
- **CLI AI coding agents** (off by default, users opt *in*): Copilot, Codex,
  Gemini, opencode, Aider.

### 1b. Add the install step

Place the `RUN` block in the matching section of the file (the sections mirror
the arg blocks). Follow the guard pattern used by every other entry:

**npm-based tool** (needs `INSTALL_NODE=1`):
```dockerfile
# --- <Tool> (via npm) ---------------------------------------------------------
RUN if [ "$INSTALL_<TOOL>" = "1" ]; then \
        if command -v npm >/dev/null 2>&1; then npm install -g <npm-package-name> ; \
        else echo "WARN: INSTALL_<TOOL>=1 but Node is missing (INSTALL_NODE=0) — skipping"; fi ; \
    else echo "INSTALL_<TOOL>=0 — skipping <tool>"; fi
```

**pipx-based tool** (needs `INSTALL_PYTHON=1`):
```dockerfile
# --- <Tool> (via pipx) -------------------------------------------------------
RUN if [ "$INSTALL_<TOOL>" = "1" ]; then \
        if command -v pipx >/dev/null 2>&1; then \
            PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install <pypi-name> ; \
        else echo "WARN: INSTALL_<TOOL>=1 but pipx is missing (INSTALL_PYTHON=0) — skipping"; fi ; \
    else echo "INSTALL_<TOOL>=0 — skipping <tool>"; fi
```

**Binary download** (pinned release, like glab / yq):
```dockerfile
ARG <TOOL>_VERSION=x.y.z
# --- <Tool> (pinned — bump <TOOL>_VERSION to update) ------------------------
RUN if [ "$INSTALL_<TOOL>" = "1" ]; then \
        ARCH="$(dpkg --print-architecture)" \
        && curl -fsSL "https://example.com/releases/v${<TOOL>_VERSION}/tool_linux_${ARCH}" \
             -o /usr/local/bin/<tool> \
        && chmod 0755 /usr/local/bin/<tool> ; \
    else echo "INSTALL_<TOOL>=0 — skipping <tool>"; fi
```

---

## 2. `docker-compose.yml`

Forward the new build arg in the `build.args` block, alongside the others in
the same category:

```yaml
INSTALL_<TOOL>: ${INSTALL_<TOOL>:-0}
```

The `:-0` default must match the Dockerfile's ARG default.

---

## 3. `.env.example`

Add the flag with a one-line comment, in the matching category block:

```sh
# <Tool description> (needs INSTALL_NODE=1)   ← list prereqs if any
INSTALL_<TOOL>=0
```

---

## 4. Control plane command catalog — `image/controlplane/server.py`

**This is the step most likely to be missed.** The `COMMAND_CATALOG` list in
`server.py` is what drives the `/api/commands` endpoint, which populates the
spawn-agent dropdown in the UI. If the tool is not in this list it will never
appear in the dropdown, regardless of whether it is installed.

Add an entry to the appropriate group in `COMMAND_CATALOG`:

```python
COMMAND_CATALOG = [
    # AI coding agents
    ("claude",     "claude --dangerously-skip-permissions"),
    ("<binary>",   "<launch command>"),   # ← add here
    ...
]
```

The first element is the binary name passed to `shutil.which` — it must exactly
match what lands on `$PATH` after install. The second element is the full command
shown in the dropdown and sent to `tmux new-session`.

---

## 5. `README.md`

Two places to update:

**a) The `INSTALL_*` flags table** in the "Choosing toolchains" section:

```md
INSTALL_<TOOL>=0  # <Tool>  (needs INSTALL_NODE=1)
```

**b) The Files table** near the bottom — update the `image/Dockerfile` row to
include the new tool in the parenthetical list of AI agents / utilities.

---

## 6. `image/CLAUDE.md`

Update the **Toolchains** section so Claude Code (running inside the container)
knows the tool may be present:

```md
- CLI AI agents: Claude Code, ..., <Tool>, ...
```

---

## Checklist summary

| # | File | What to do |
|---|------|------------|
| 0 | — | Verify exact package/binary name on the registry |
| 1a | `image/Dockerfile` | Add `ARG INSTALL_<TOOL>=0` in the right block |
| 1b | `image/Dockerfile` | Add guarded `RUN` install step in the matching section |
| 2 | `docker-compose.yml` | Forward `INSTALL_<TOOL>: ${INSTALL_<TOOL>:-0}` |
| 3 | `.env.example` | Document the flag with a comment |
| 4 | `image/controlplane/server.py` | Add `("<binary>", "<command>")` to `COMMAND_CATALOG` |
| 5a | `README.md` | Add to the `INSTALL_*` flags table |
| 5b | `README.md` | Update the Files table Dockerfile description |
| 6 | `image/CLAUDE.md` | Add to the Toolchains list |
