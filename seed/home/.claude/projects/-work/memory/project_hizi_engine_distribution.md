---
name: project_hizi_engine_distribution
description: "hizi-engine is distributed as a Docker image, not npm; the npm publish was a vestigial monorepo holdover"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f20ad19-c981-41a1-af69-447d8c926ee5
---

`@hizi.io/engine` (repo `code.hoelle.games/hizi/hizi-engine`) is distributed/run as a **Docker image** (`build-docker` → `publish-docker` → `deploy-docker-*` in `.gitlab-ci.yml`), NOT as a consumed npm package.

Nothing imports the bare `@hizi.io/engine` package — the creator and others depend on `@hizi.io/engine-generator` and `@hizi.io/engine-sdk`, which are separate packages. The old `publish-npm` job (publish to private registry `code.hoelle.games:7081` on `v*` tags) was a leftover from the `packages/*` monorepo era (cross-publishing siblings); after the monorepo split it had no consumer.

**Why:** the npm publish failed with `ERR_STRING_TOO_LONG` — no `files` whitelist meant `npm publish` packed the whole tree incl. git-tracked game assets `config/` (200 MB) + `config-unused/` (211 MB) → ~430 MB tarball that exceeds V8's max string length.

**How to apply:** publishing the compiled engine (RNG, certified/progression logic) served no consumer and is best avoided. Fix = drop the `publish-npm` job (MR !84), not slim the package. The standalone `build` job (tsc) was kept as a compile gate. Relates to [[project_engine_sdk_release]].
