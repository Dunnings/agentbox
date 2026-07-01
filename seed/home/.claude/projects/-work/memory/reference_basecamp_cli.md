---
name: basecamp-cli
description: Basecamp CLI is installed and authenticated; binary at ~/.local/bin/basecamp (not on non-interactive PATH)
metadata: 
  node_type: memory
  type: reference
  originSessionId: b52cc232-50eb-4afb-b922-a9abd0727b46
---

The Basecamp CLI (plugin `basecamp@37signals`) is installed and authenticated (launchpad OAuth, account Hölle Games #4718627 set as global default). The binary is at `~/.local/bin/basecamp`, which is NOT on the non-interactive shell PATH — invoke it as `~/.local/bin/basecamp ...`. Use the `basecamp` skill for command reference.

Note: agentbox has a global git rewrite `url."https://github.com/".insteadOf "git@github.com:"` (added 2026-07-01) because the container has HTTPS-only GitHub auth; this is what makes `claude plugin install` from GitHub work.
