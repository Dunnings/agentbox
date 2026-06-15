---
name: project_engine_sdk_release
description: How @hizi.io/engine-sdk is released and propagated to dependent repos
metadata: 
  node_type: memory
  type: project
  originSessionId: 57203ccc-d4f1-429f-a050-e45823800a19
---

`@hizi.io/engine-sdk` (repo `hizi/hizi-engine-sdk` on GitLab) publishes to public npm via CI: the `publish` stage runs only on `$CI_COMMIT_TAG`, so a release = bump `version` in package.json (MR to main), then push an **annotated** tag `vX.Y.Z` on the merge commit. Pushing the tag triggers the npm publish.

Propagating a new SDK version to dependents follows a fixed pattern — edit **package.json only** (lockfiles are left stale by the team; e.g. hizi-engine's lock pinned 0.1.9 while spec was ^0.2.0): bump the `@hizi.io/engine-sdk` spec to `^X.Y.Z` **and** bump the consumer's own `version` by a patch. Dependents:
- `hizi/hizi-engine` (`@hizi.io/engine`) — tracks each SDK release.
- `hizi/hizi-engine-creator` (`@hizi.io/creator`) — tracks each SDK release.
- `hizi/hizi-engine-tester` — private; crossed to `^0.2.0` on 2026-06-03 and `^0.2.3` on 2026-06-10 (David asked). Its bumps touch the dep spec only — its own `version` stays `0.1.0`.

See [[feedback_mr_reviewer]] (add david.dunnings) and [[project_hizi_creator_testing]].
