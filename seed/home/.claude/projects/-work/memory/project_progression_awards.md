---
name: progression-awards-shape
description: progressionAwards is nested (counter → step index → fractional increment) at the entry level; flat only inside per-win results; datamodels !226 + hizi-engine !88 fix the stores
metadata: 
  node_type: memory
  type: project
  originSessionId: a6f6b04a-8bfa-4854-9a4a-2ec9c805fc4c
---

`progressionAwards` has two shapes by layer: entry-level (entry DBs, generator
output, datamodels game-content stores) is `Record<string, Record<number,
number>>` — counter name → scenario step index → fractional increment; the
old flat `Record<string, number>` type in datamodels was always wrong (every
writer emits nested; creator's editor writes `{0: value}`). Flat
`Record<string, number>` is correct only inside a win object in a scenario
step (creator `slot-types/src/result.ts`).

Ongoing (as of 2026-06-11): infrastructure/datamodels !226 + dependent
hizi-engine !88 (author cruehringer, David reviewer). After my first review,
!226 was rewritten (RC4): datamodels no longer validates nested payloads at
all — `GameContentEntryData` deleted, `data` is an opaque required
`JsonObject`, README declares nested validation the consumer's job. Dynamo
items stay FLAT (data spread into the item; read destructures addressing
fields out). By 2026-06-12 (RC5): reserved-key write guard added in Dynamo
mapEntryForWrite (covers putEntry + batch, tested for all 10 keys) and !88
synced (RC5 bump, dead top-level fallback in gameAPI.ts deleted) — both
resolved; !226 green, nothing blocking from my side. !88 pipeline red only
because RC5 isn't published yet (npm ETARGET) — merge !226 first. Still open
on !88: no layer validates progressionAwards shape (engine only casts;
malformed = counter silently never increments via processProgressionAwards
`perStep[stepIndex]` → undefined → skip; suggested shape check in import.ts
toEntryFields — author's call) and redacted-looking AWS creds in the
commented `.env` example.
DynamoDB game-content backend (`GAME_CONTENT_BACKEND=dynamo`) is newly being
wired up.
