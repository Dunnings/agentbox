---
name: project_hizi_gamble_collect
description: "hizi-engine /collect during card gamble — wallet has no partial-collect-keep-open; \"bank half\" is the model"
metadata: 
  node_type: memory
  type: project
  originSessionId: 16eeda71-0721-4727-9ce8-e5ca2e23459a
---

hizi-engine (`hizi/hizi-engine`, the multi-game casino backend — not the slot
engine `hizi-engine-creator`). The `/collect` endpoint for fixed-odds card
gamble lives in `src/games/fixed-odds/collect.ts` and has two paths: a
completed-round path and an in-progress (gamble) path.

Key wallet constraint: the V2 `collectWin` wire call **always closes the round**
and is the only primitive that credits the real balance — there is **no
"credit part + keep the round open"** mode. During a gamble nothing reaches the
real balance; the running win sits as the round's `amountToCollect` and only
pays out at the final `collectWin`.

So "collect half and keep gambling" is modeled as **bank half** (MR !72,
2026-06): a partial `collectAmount` locks that amount in as a protected floor
(`engineData.bankedWin`, rides on engineData at runtime — not in the SDK
`IGameResult` type), persisted via `addWin` (round stays open), no money moves.
The next gamble step (`runStep.ts`) re-stakes only `totalWin - bankedWin`.
`runStep.ts` is certified math (feeds `pfVerify` replay + RTP) — changes there
need a certification check, not just code review.

**Bust-to-bank close** (MR !78, 2026-06): if the player banks then *loses* the
remaining at-risk gamble, the finished step (`inProgress=false`) collapses
`totalWin` to the banked floor. Previously the round stayed open (manual
`/collect` / autoclose janitor). Now `placeBet.ts continuePlaceBet` detects
`wagerBustToBank` (anyWagerMode, !inProgress, banked>0, totalWin<=banked) and
**auto-collects the floor via `collectWin` and closes** — mirroring the ladder
top-rung auto-collect already in main. Gated on `!inProgress` so a ladder
mid-climb at the floor isn't force-closed. `hasUnpaidBank` still keeps the
round open only for a *real win on top of the bank* that can't be re-gambled.
The fix is wallet/lifecycle only — `runStep.ts` math untouched.

**Why:** the original bug was the in-progress path ignoring `collectAmount` and
always full-cashing-out. **How to apply:** when touching gamble collect/payout,
remember collectWin closes; use addWin to keep a round open. See
[[feedback_mr_reviewer]], [[feedback_fold_into_open_mr]].
