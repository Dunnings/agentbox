---
name: spread-limit-crash
description: 50M-sim browser crash = V8 ~125k spread-argument limit; generator 0.4.1 fix needs creator dep bump
metadata: 
  node_type: memory
  type: project
  originSessionId: 702a54a6-d533-4abd-9f7d-661edaba97b6
---

Big slot sims (~50M spins, >125k unique outcomes) crashed the creator at sim
completion with `RangeError: Maximum call stack size exceeded` — V8 throws this
when an array is spread as function arguments past ~125k elements
(`Math.max(0, ...entries)`, `push(...entries)`). Array-literal spreads
(`[...a, ...b]`) are safe; only call-argument spreads overflow.

Fixes (2026-06-10): hizi-engine-generator-ts!17 (computeOverallKpis +
computeMaxPayout) — merged, tagged v0.4.1, published to npm. Creator MR !131
carries the in-repo fixes (dbWorker, autoBalance, useChangeLog) AND the dep
bump `^0.2.2` → `^0.4.1` (creator 0.1.15); note the bump also pulls in the
0.3.x/0.4.x generator changes (looseScenarioCap, gamble-config). Watch for
this bug class in any code iterating full entry pools. Gotcha: `npm pkg set`
mangles scoped keys with dots (`@hizi.io/...`) — edit package.json directly.
creator's package-lock.json is gitignored on purpose.

Round 3 (same day): re-run hit a real 10.0/10.0 GB OPFS quota. Creator MR !133:
(a) scenarios now stored codec-compressed (short keys + int symbols) from the
aggregator on — 581→321 B/scenario (1.8×) pre-brotli; safe because the codec
(engine-sdk scenarioCodec, canonical) is lenient + idempotent, so the
archive-time compress pass and mixed files are no-ops; editor dbWorker expands
on read via scenarioCtx (gameType+symbolMap) from SlotApp/config.json;
(b) looseScenarioCap exposed as a General-tab checkbox → generator in all 3 sim
paths. Caveat: sim scenarios bake symbol ints at sim time — addressed by MR !134
(branched from !133, merge !133 first): any builder-config change after a
completed run auto-discards results (configJson snapshot in SimulationStatus),
warns in the Simulate tab, and locks the Edit stage via editReady.
BuilderShell i18n keys are unprefixed ("stepper.*"); slot panel keys are
"slot.*". MR !133 also got deploy:preview fixes (11143d5 + 04cabe3): the sim container
builds from repo root with a MINIMAL context — .dockerignore excludes all of
node_modules and re-includes only specific @hizi.io subtrees, and the
Dockerfile copies only slot-types/slot-engine/containers/sim + those subtrees.
New imports in containers/sim/*.ts need BOTH a Dockerfile COPY and a
.dockerignore re-include (engine-sdk broke deploy:preview twice). Docker (dind)
works in agentbox: verify with a full `docker build -f containers/sim/Dockerfile .`
before pushing — hand-replicating the COPY layout misses context filtering.
Separate: `npm run generate` CLI is broken on main (tsx +
fast-json-patch "Cannot find module './src/core'"), pre-existing.

Round 4: 50M on the !133 preview STILL hit 9.9/10.0 GB (verbose total was
≥18 GB; minify ~1.8× isn't enough; per-entry caps can't bound the long tail).
I built a global scenario byte budget (generator maxScenarioBytes + creator
quota-derived budget, MRs generator!18 + creator!135) but **David rejected the
approach** (2026-06-10): it's okay to let the browser fail on quota — do NOT
silently truncate scenario variety to fit storage. Both MRs closed, branches
deleted. Remaining levers he accepts: minify (!133), looseScenarioCap
checkbox, lower Scenario Count Cap, free disk. MR rule: assignee
david.dunnings, NO reviewer. Endgame: David squash-merged !134 (stacked on
!133), which carried !133's whole diff onto main (6e1e3d4) — !133 closed as
redundant, both branches deleted. Stacked-MR gotcha: merging the top of a
stack with squash lands the whole stack; the lower MR then shows phantom
conflicts and must be closed, not rebased. OPEN QUESTION from David: sims
reach 100% (scenarios streamed to OPFS fine) yet quota blows at the end —
suspects duplication; likely culprit = generator.end() one-shot entries.jsonl
write + final flush, NOT a copy. To investigate next.

Follow-on (same day): 50M run then hung at 100% with QuotaExceededError —
`finalize()` in the sim dbWorker was an uncaught async; Worker.onerror never
fires for unhandled rejections, so the UI waited forever. Also generator 0.3.0's
zero-win scenario cap (default 2000) ignores the user's Scenario Count Cap.
Both fixed in creator MR !132 (dbError message + pass cap as
maxScenariosPerZeroWinEntry). Slot sim scenario flow: sim workers → aggregator
(caps per batch only!) → slot/simulation/dbWorker → HiziEngineGenerator streams
scenarios.jsonl to OPFS /game during sim; entries.jsonl written in one shot at
generator.end() AFTER 100%.
