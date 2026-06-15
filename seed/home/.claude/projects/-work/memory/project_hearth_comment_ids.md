---
name: project_hearth_comment_ids
description: "Hearth seed comment ids (c1..c7) are NOT globally unique — comments PK is seq, not id"
metadata: 
  node_type: memory
  type: project
  originSessionId: fc318820-897c-470a-9719-8ecfd0153fc2
---

In Hearth, the `comments` table's primary key is `seq` (autoincrement), not
`id`. The seeded comment `id`s (`c1`, `c2`, … `c7`) are only unique *within* an
issue — the same id repeats across issues. So **never key per-user/global state
on a bare comment id**. The Activity feed (MR !23) hit this: marking one comment
read marked every comment sharing that id. The search index (fixed in MR !32)
hit it too: `commentDoc` keyed `search_index.ref_id` on the bare comment id, so
Postgres `reindexAll()` crashed on the PK and D1 silently overwrote docs. Fix
in both cases = composite id `${issueId}:${c.id}`. Anything that needs a globally-unique handle for a comment
must combine it with the issue id (or use `seq`, which isn't currently exposed
through the repo/projection layer). Issue ids (`i_*`), user ids, project ids are
globally unique. Related: [[project_hearth_search]].
