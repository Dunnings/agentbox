---
name: project_haw_enhancement_epic
description: "Hold & Win enhancement epic for the final 2 betgames games — 4 asks, status + chosen designs"
metadata: 
  node_type: memory
  type: project
  originSessionId: e5715ea5-2ac3-4693-a31c-85b0e49fb814
---

David is enhancing Hold & Win in `hizi-engine-creator` to build the final 2 betgames games of the year. Four capabilities were requested:

1. **Unlock new cells during gameplay** by collecting enough symbols — NOT STARTED. Most invasive (redefines playable area for placement + full-screen). Open design fork: unlock trigger = all coins vs a dedicated key symbol; cell model = stage groups vs per-cell thresholds.
2. **Symbol adds its value to a random number of landed coins, sticky or not** — DONE (MR !142).
3. **Same but a multiplier** — DONE (MR !142, unified with #2).
4. **More nuanced collector with different multipliers** — NOT STARTED. Open fork: collector tiers (distinct symbols, each own multiplier) vs one collector with a weighted multiplier roll vs both.

Asks #2+#3 shipped together as the **booster** mechanic (`holdAndWin.boosters[]`, `mode: 'add'|'multiply'`) in MR !142 (`feat/haw-booster-symbols`). That MR also fixed: special symbols (collector/booster) now reset lives when they land by themselves (previously a lone collector with nothing to sweep burned a life). Design default to revisit: a sticky booster is inert as a prize (contributes 0 to collector sweep).

H&W engine lives in `slot-engine/evaluation/holdAndWin.ts` (`evaluateHoldAndWinSpin` — two-pass: place coins → collector; boosters inserted between). Respin symbol set built in `slot-engine/index.ts` (`buildHoldAndWinSymbols` / fallback in `handleHoldAndWinFeature`). All engine randomness draws from global `Math.random()` (seeded in tests via `withSeededRandom`). Surfacing chain for any new sub-mechanic: types (`slot-types/src/slotConfig.ts` + `result.ts`), engine, builder UI (`src/slot/components/feature/FeatureMechanicsTab.tsx`), validation (`src/slot/utils/validateConfig.ts`), AI tool (`set_hold_and_win` in `src/ai/contexts/slot.ts`), EN/DE i18n, scenario doc (`src/ai/scenarioFormats.ts`), unit tests (`slot-engine/__tests__/units.test.ts`).

See [[feedback_mr_description_structure]], [[feedback_glab_mr_flags]], [[feedback_mr_reviewer]].
