---
name: basestake-storage
description: hizi-engine no longer sends buyFeatureInfo; base stake lives on engineData.baseStake (MR !87)
metadata: 
  node_type: memory
  type: project
  originSessionId: ad437654-36e6-4be3-a8ed-5a5475eafdf6
---

Merged 2026-06-11 (hizi-engine MR !87): buy-feature rounds debit the full feature price (`targetPrice × stake`) directly with **no `buyFeatureInfo`** in `IDebitInformation`, so the RGS reports `gameRoundInfo.stake === baseStake === price`. The player's chosen stake (the basis for all win math, wager arithmetic, exposure cap, history multipliers) is stored by the engine on `engineData.baseStake` via `src/games/baseStake.ts` (narrow-cast pattern, like `bankedWin` in [[hizi-gamble-collect]]'s banking.ts). Stamped on every initial bet (fixed-odds/mines/keno), explicitly propagated in both `runStep.ts` files because continuation draws build a fresh result object. All readers use `getStoredBaseStake(result) ?? gameRoundInfo.baseStake` — the fallback covers rounds started before the change; don't remove it until those have drained. RGS side must accept the plain price debit (no stake-ladder validation on debitAmount) — engine-only change. David followed up on main with `fix for noninteger buyfeature prices` (targetPrice × stake can land off the smallest-currency-unit grid).
