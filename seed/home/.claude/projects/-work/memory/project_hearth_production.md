---
name: project_hearth_production
description: "Hearth 1.0.0 production setup — env-admin bootstrap, SEED_DEMO dev-only, D1 Time Travel backups, squashed migrations"
metadata: 
  node_type: memory
  type: project
  originSessionId: fc318820-897c-470a-9719-8ecfd0153fc2
---

Hearth's 1.0.0 production model (MRs !28 de-demo + !29 migration squash):

- **Bootstrap an empty DB:** `SEED_DEMO` set → full sample workspace (DEV ONLY);
  else `ADMIN_USERNAME`/`ADMIN_PASSWORD` (Worker secrets) → one admin (PROD);
  else empty + warn. The rich demo seed (`server/data.mjs`, DEMO_ACCOUNTS.md)
  is reachable only via `SEED_DEMO`, which `npm run dev`, `cf:dev`, and the
  screenshot harness pass — **never set SEED_DEMO in prod**.
- **/api/reset** is dev-only (gated on `SEED_DEMO`; 404 in prod). The hidden
  `/reset` page only works in dev.
- **Real clock:** the pinned 2026-06-01 demo clock is gone — `stamp()` and web
  `ago()` use real time; the dev seed dates relative to `Date.now()`.
- **Backups = D1 Time Travel** (chosen): automatic 30-day point-in-time history,
  no cron. Restore: `wrangler d1 time-travel restore hearth --timestamp=...`.
  See docs/OPERATIONS.md.
- **Migrations squashed** to a single `0001_init` (D1) / `001_init` (Postgres) —
  assumes a FRESH prod D1 (the demo D1 is disposable). An existing DB with
  0001–0010 already in d1_migrations won't pick up the new single init by name.

**Cutover to go live:** recreate the prod D1 fresh, `wrangler d1 migrations
apply hearth --remote`, set secrets SESSION_SECRET + ADMIN_USERNAME +
ADMIN_PASSWORD (not SEED_DEMO), deploy; first request creates the admin.
Related: [[project_hearth_settings_users]], [[project_hearth_d1_migrations]].
