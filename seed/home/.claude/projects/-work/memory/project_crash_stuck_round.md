---
name: crash-stuck-round
description: Crash rounds stranded open when V2 endGameRound fails; fix in hizi-engine MR !86; prod round 521a3546… may need manual close
metadata: 
  node_type: memory
  type: project
  originSessionId: 24371274-8169-4396-b06d-7463918c733d
---

Crash (e.g. `crash-98`) rounds could get permanently stuck `open` with the protected-data secret wiped → every placeBet/collect returns code 13 "Round not active". Root cause: `endCrashRound` cleared the secret even when `endGameRound` failed (non-200 wasn't even detected). Fix on MR !86 (hizi-engine, branch `fix/crash-stuck-open-round`, opened 2026-06-10): secret only cleared on confirmed close; resume/collect close secretless open rounds; setCrashSecret failure settles inline.

**Production follow-up:** round `521a3546801a48b2b46b29589c1d449e` (tenant T-9THSTREET, player 7999d584…) was the incident round — committed crash point ≈1.249× vs 2× auto-cashout, so bet legitimately lost; round self-heals on the player's next placeBet once !86 deploys, or close manually via `endGameRound`. Related: [[hizi-engine-distribution]] (engine ships as Docker image).
