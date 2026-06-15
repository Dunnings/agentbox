---
name: project_hizi_creator_testing
description: "hizi-engine-creator had no tests/runner; slot-engine now has characterisation tests via Node's built-in runner + tsx"
metadata: 
  node_type: memory
  type: project
  originSessionId: 59036174-5a9a-480c-80aa-ff08509fc9ee
---

`hizi-engine-creator` (code.hoelle.games/hizi/hizi-engine-creator) historically
shipped with **no test runner and zero tests**, and no ESLint/Prettier config
(only `tsc --noEmit`). As of MR !115 (branch `refactor/slot-engine-cleanup`,
2026-06-07) the slot engine has a characterisation safety net:

- `npm test` runs `tsx --test "slot-engine/__tests__/**/*.test.ts"` — uses
  **Node's built-in test runner via the existing `tsx` devDependency, no new
  test framework**. Keep it that way unless there's a strong reason.
- Tests live in `slot-engine/__tests__/`. Approach: seed `Math.random` with a
  mulberry32 PRNG (`_helpers.ts`), run each `src/slot/templates/*.json` through
  `playGame`, assert golden fingerprints (total win + result count + stream
  hash). These are byte-stable and exercise most engine paths.

Engine boundary facts: `@hizi.io/slot` is a **tsconfig/webpack path alias to
`slot-engine/index.ts`, NOT a published npm package** (repo is `private`), so
narrowing its export surface is safe. `@hizi.io/slot-types` is likewise a path
alias (`slot-types/src/index.ts`), not an installed node_module — only `tsx`
(which honours tsconfig paths) and the webpack build resolve it. Related:
[[project_hizi_gamble_collect]], [[user_david_dunnings]].
