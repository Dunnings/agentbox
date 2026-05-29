# agentbox

You are running inside a dedicated Docker container (agentbox). The host
filesystem is not mounted. Any credentials available to you are scoped to the
specific bot/PAT wired up in `.env` — act accordingly. The blast radius of a
mistake is bounded by what those credentials are allowed to do, not by
per-action confirmations.

## VCS access

Whichever of these are configured will already be authenticated — do not run
`gh auth login` or `glab auth login`.

- **GitHub**: enabled when `$GITHUB_TOKEN` is set. `git` over HTTPS to
  `github.com` works via `~/.netrc`; `gh` picks up the token automatically.
  Use HTTPS remotes (`https://github.com/...`).
- **GitLab**: enabled when `$GITLAB_TOKEN` and `$GITLAB_HOST` are set. `git`
  over HTTPS and `glab` are authenticated via `~/.netrc` and
  `~/.config/glab-cli/config.yml`. Use HTTPS remotes
  (`https://$GITLAB_HOST/...`).

If a host is not configured, treat it as unavailable — do not try to push or
clone from it.

## Default workflow for changes

**Every session that modifies code ends with an open PR / MR.** The user
reviews and merges from there — they are not watching the session live, so
work that stays on a local branch is invisible to them. Pushing the branch
and opening the PR/MR is part of finishing the task, not a follow-up step;
do it without being asked. The only reasons to skip it:

- The task was read-only (investigation, questions, no code changes).
- The user explicitly said not to push or not to open a PR/MR.
- The relevant host (`GITHUB_TOKEN` for GitHub, `GITLAB_TOKEN` for GitLab)
  is not configured, so pushing is impossible.

If the work is incomplete or blocked when the session ends, still push and
open a **draft** PR/MR that describes what is done and what is left.

Use `git worktree` so each branch lives in its own directory. The main
checkout stays on the default branch as a clean reference; feature work
happens in sibling worktrees. This lets concurrent tasks share one clone
without stomping on each other's index or `HEAD`.

1. `cd /work && git clone <repo-url>` — only the first time per repo. Leave
   `/work/<repo>` on the default branch; never commit to it directly.
2. From the main checkout, create a worktree for the feature branch:
   `git worktree add ../<repo>.worktrees/<feature-branch> -b <feature-branch>`
3. `cd ../<repo>.worktrees/<feature-branch>` and make your changes there.
4. Commit, then `git push -u origin <feature-branch>`.
5. Open a PR / MR (`gh pr create --fill` or `glab mr create --fill`, or
   `--draft` if work is incomplete) and report the URL to the user as the
   final output of the session. Do this even if the change feels small or
   obvious — the PR/MR is how the user sees what you did.
6. After the branch is merged or abandoned, clean up:
   `git worktree remove ../<repo>.worktrees/<feature-branch>` (run from the
   main checkout). Use `git worktree list` to see what's currently checked
   out, and `git worktree prune` if a directory was deleted manually.

## Filesystem

- `/work` — workspace. Clone repos here as `/work/<repo>` and put feature
  worktrees alongside them as `/work/<repo>.worktrees/<branch>`. Persists
  across container restarts.
- `/home/dev` — your home. Contains caches (`.npm`, `.cargo`, `.bun`), agent
  state (`.claude`), bash history. Persists.
- `/tmp` — tmpfs, wiped on restart. Use for throwaway files.
- `/usr/local` — system toolchains. Treat as read-only.

## Environment variables

Populated from the host `.env` file at container start (any may be unset):

- `GITHUB_TOKEN` — optional GitHub PAT.
- `GITLAB_HOST` / `GLAB_HOST`, `GITLAB_TOKEN` — optional GitLab host + PAT.
- `GIT_USER_NAME`, `GIT_USER_EMAIL` — commit identity (already applied via
  `git config --global`).

For Claude Code, run `claude login` once; auth persists in `/home/dev/.claude`.

## Toolchains

git, `jq`, tmux, and the `python3` interpreter are always present. Everything
else is opt-in at build time (via `INSTALL_*` flags in `.env`) and may or may
not be installed — **check with `command -v` before assuming one exists**:

- Languages/runtimes: Node.js 22 + npm, Bun, Rust (`rustc`, `cargo`), Go,
  Deno, Ruby, and Python dev tooling (pip, pipx, `uv`).
- Utilities: `gh`, `glab`, `docker` (+ `compose`/`buildx`), `rg`/`fd`/`fzf`,
  `yq`, `shellcheck`, and DB clients (`psql`, `sqlite3`, `redis-cli`).
- CLI AI agents: Claude Code, GitHub Copilot, OpenAI Codex, Google Gemini,
  Aider.

Whatever is installed is on `$PATH`.

## Docker

If the Docker CLI is installed (it's opt-in — `command -v docker` to check),
`docker`, `docker compose`, and `docker buildx` are wired up to a sidecar
Docker daemon — `DOCKER_HOST=tcp://dind:2375` is set automatically. You
are NOT talking to the host's Docker daemon:

- Containers / images / volumes you create are isolated inside the dind
  sidecar. They do not appear in `docker ps` on the host.
- You cannot mount host filesystem paths into containers — only paths
  inside the dind sidecar exist from its perspective.
- Bind-mounting `/work` or `/home/dev` into a container does NOT work the
  way it would on the host — those volumes are mounted into agentbox,
  not into dind. If you need a repo's files inside a launched container,
  either build them into an image, copy them in with `docker cp`, or use
  a named volume.
- `docker pull` and `docker build` populate the dind volume
  (`agentbox-dind-data`), not the host cache.

If `docker` commands fail with "Cannot connect to the Docker daemon",
the dind sidecar is probably still starting — wait a few seconds and
retry, or check it with `docker info`.

## Out-of-scope actions

- Do not attempt to reach the host or escape the container.
- Do not commit or log any token from the environment.
- Do not mutate anything outside `/work` and `/home/dev` unless explicitly
  asked.
