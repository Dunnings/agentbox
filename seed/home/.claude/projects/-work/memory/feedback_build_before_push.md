---
name: build-before-push
description: "Always run the project build (and tests if present) before committing and pushing, to catch errors like unused imports before CI does."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cec4fdbf-02e8-4430-a834-261980080e34
---

Always build (and run tests if available) before committing and pushing. Don't rely on CI to catch compile errors, type errors, or lint failures.

**Why:** A TypeScript unused-import error broke the CI pipeline on MR !41 — caught only after push, wasting a pipeline run.

**How to apply:** Before any `git commit` + `git push`, run the project's build command (e.g. `npm run build`, `tsc -b`, etc.) and verify it exits 0. If tests exist, run those too. Only push on a clean build.
