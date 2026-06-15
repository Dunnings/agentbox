---
name: buyfeature-tag-weights
description: entrypool/stakeboost per-tag weighting semantics (generator 0.4.2 + creator !137); generator test.ts has a stale pre-existing failure
metadata: 
  node_type: memory
  type: project
  originSessionId: 00202c52-9b9b-44c1-b341-ed46b9b585d1
---

Buy-feature meta-tag weightings were collected by the creator UI but consumed nowhere (bug reported 2026-06-10). Fix landed as two MRs: hizi-engine-generator-ts!19 (`resolveBuyFeatures` gains optional `metaTagWeights: Record<string, number>`, v0.4.2 — publish requires annotated tag `v0.4.2` after merge) and hizi-engine-creator!137 (UI math in `resolveEntries` + save path + dep bump ^0.4.2, creator 0.1.17). 0.4.2 is published on the registry (confirmed 2026-06-12; fresh `npm install` resolves it and creator builds green — typecheck errors against an older installed generator are environment staleness, not code).

**Semantics:** tagged entry weight = DB weight × weighting of its matching tag (highest wins for multi-tag entries; unlisted/default = 1); stakeboost composes with `chanceMultiplier`; per-entry `weightOverrides` replace the scaled weight. All-1 weightings = old behaviour.

**Gotchas:** `npx tsx test.ts` in generator-ts fails on main at "freespin rtpContribution: expected 40, got 8" — stale test vs a gameRtp refactor, CI only runs build+lint so it never surfaces. CLI `npm run generate` in creator never resolves entrypool/stakeboost buys at all (browser-only save path); pre-existing gap. The AI editor tools (`add_buy_feature`) only accept tag names, not weightings.

Related: [[hizi-engine-distribution]], [[engine-sdk-release]]
