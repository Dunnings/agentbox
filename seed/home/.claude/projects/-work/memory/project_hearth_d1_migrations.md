---
name: project-hearth-d1-migrations
description: "hearth's Cloudflare D1 schema/migration gotchas (prod deploys) and the fix"
metadata: 
  node_type: memory
  type: project
  originSessionId: fc318820-897c-470a-9719-8ecfd0153fc2
---

hearth (code.hoelle.games/hearth/hearth) deploys a Cloudflare Worker backed by
**D1** (prod) with the schema in `migrations/0001_init.sql`. Local dev uses
Postgres (`server/db/migrations/`). The worker **self-seeds** from
`server/data.mjs` on first request when the DB is empty.

In early mode we **consolidate the whole schema into `0001`** and wipe freely
rather than keeping incremental migrations. Two gotchas this caused (both bit
prod, twice):

1. **Editing `0001` does nothing to an existing DB.** `wrangler d1 migrations
   apply` skips any migration already in the `d1_migrations` journal. So after
   rewriting `0001`, an existing D1 keeps its old schema → runtime 500s.
2. **Stale journal + missing tables = silent empty prod.** A DB can end up with
   `d1_migrations` marking `0001` applied but **0 actual tables** (e.g. a prior
   partial/failed apply). `migrations apply` then says "No migrations to apply"
   and the deploy ships a schema-less DB → every endpoint 500s
   ("database not initialized" / missing-table on `/api/me`).

**Fix for a broken prod D1** (keeps the same db id):
```
wrangler d1 execute hearth --remote --command "drop table if exists d1_migrations"
wrangler d1 migrations apply hearth --remote
# verify: select name from sqlite_master where type='table'
```
or apply the schema directly: `wrangler d1 execute hearth --remote --file ./migrations/0001_init.sql`.

3. **Table-rebuild migrations cascade-delete children on REMOTE D1 (not in
   miniflare).** Migration `0004` dropped `projects.kind` via the SQLite
   rebuild dance (create projects_new, copy, `drop table projects`, rename).
   `DROP TABLE` does an implicit row-delete that fires `ON DELETE CASCADE`, so
   on populated prod it wiped `issues`/`comments`/`project_clients` (projects +
   users survived) → "3 projects but no threads/tasks". `PRAGMA
   defer_foreign_keys` does NOT prevent the cascade actions, and **local
   miniflare doesn't enforce the cascade so it passes the local test** — only
   remote D1 bites. Fix: re-seed prod via the **Reset demo** button (POST
   /api/reset truncates + re-inserts; verified restores). Going forward: on a
   table with `ON DELETE CASCADE` children, prefer additive migrations or leave
   a column vestigial rather than rebuilding the parent on a populated DB.

**How to apply: add a NEW migration file (`0002`, …), never edit `0001`.** Now
that the support→thread rebuild is baked into `0001`, future changes are simple
ADD COLUMN / new-table migrations that auto-apply on deploy with no wipe.
Per-MR previews recreate their D1 each deploy (ci/deploy-review.sh) so they
always get the current schema. Consider hardening the prod `deploy` job to
verify the table count after `migrations apply` and fail loudly. See
[[feedback-fold-into-open-mr]].
