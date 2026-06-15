---
name: project_hearth_search
description: Hearth search uses SQLite FTS5 in D1 (+ Postgres FTS in dev); D1 does support FTS5
metadata: 
  node_type: memory
  type: project
  originSessionId: fc318820-897c-470a-9719-8ecfd0153fc2
---

Hearth's global search (MR !20) is built on **SQLite FTS5 in D1** for prod
(co-located with the Worker, zero new infra/cost) and **Postgres full-text
search** in dev — chosen over Orama/Meilisearch/Typesense because those add
in-memory-per-isolate staleness or an external service, both bad fits for live
write-heavy data on Workers.

**Key fact (corrects a common assumption):** Cloudflare D1 *does* support the
FTS5 module (incl. `fts5vocab`) — confirmed in the official D1 SQL-statements
docs and verified working on local miniflare. Caveat: D1 export doesn't support
virtual tables (drop + recreate to export).

Design: one unified `search_index` table (cols: kind, ref_id, parent_id,
project_id, visibility, org, title, body). Shared doc-builders + query parsing
in `server/search.mjs`, imported by both `worker/db.mjs` (bm25/highlight/snippet)
and `server/repo.mjs` (ts_rank/ts_headline). Visibility enforced *in SQL*: staff
see all; clients limited to public docs in their visible projects + staff people;
internal comments never leak. Index is incrementally updated on create, rebuilt
on seed/reset, and lazily backfilled on first search if empty (so prod
self-populates after the migration ships — no reseed). Highlight markers are
\x02/\x03, turned into `<mark>` client-side.

Related: [[project_hearth_d1_migrations]].
