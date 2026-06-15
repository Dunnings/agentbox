---
name: project_gamble_runtime_migration
description: "Card/ladder gamble moved from baked entries to runtime engine synthesis — 3 MRs, one cleanup follow-up"
metadata: 
  node_type: memory
  type: project
  originSessionId: 39b2ed5c-304e-432e-b689-7c835e9c5f31
---

Card + ladder gamble were moved out of the baked "fixed odds table"
(weighted `card_*`/`ladder_*` wager features in entries.jsonl/scenarios.jsonl)
into runtime synthesis in hizi-engine, driven by config.json flags
(`enableCardGamble`, `enableLadderGamble`, `ladderMultipliers`, `ladderLives`).
Card odds are hardcoded in the engine (red/black 2×, suit 4×); clean cut-over
(no DB fallback for old baked archives — they must be re-exported).

Three MRs opened 2026-06-05 (David reviewer):
- hizi-engine !73 — `games/fixed-odds/gamble.ts` synthesis + `applyGambleConfig`.
- hizi-engine-generator-ts !16 — adds the 4 fields to `IGameConfig`, bumps 0.3.0→0.4.0.
- hizi-engine-creator !112 — writes flags, removes baked-entry injection.

**Ladder is a faithful port of slot-backend** (`code.hoelle.games/slot-backend/slot-backend`,
`CertifiedLogic.ladderGamble`): stateful climb, start on the 1× rung with
`ladderLives` (default 3), fair up/down bet, loss burns a life + steps down,
last-life loss → rung 0 (lose everything). Top rung **auto-collects**
(`collectWin` + close round, like slot-backend). State on
`engineData.ladderState`; win is absolute (`mult[rung]×baseWin`). NOT the
independent per-rung bets the first cut shipped. Card gamble = relative 2×/4×,
kept as-is. Card and ladder are mutually exclusive per round. RGS confirmed: a
`wagerWin` scraps the wager value and awards the new win (can be < wagered), so
ladder down-steps lowering the collectable are fine.

Generator MR !16 merged + **published as v0.4.0** (the generator publishes only
on a `vX.Y.Z` tag — `if: $CI_COMMIT_TAG` — merging to main does NOT publish).
hizi-engine bumped to `^0.4.0` and the local `IGameConfig` gamble shim collapsed
back to a plain re-export (done on MR !73).

Engine `loadConfig` now forwards `ladderMultipliers` + `ladderLives` (gated on
the ladder being active) so the client can render the rungs (MR !73). Creator
MR !112 now warns when `ladderMultipliers` would disable the ladder (mirrors the
engine's validation). No open follow-ups.
