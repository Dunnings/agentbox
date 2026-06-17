---
name: reference_slot_backend_version_branches
description: How slot-backend ships fixes to a specific deployed version (per-version maintenance branches + X-N patch bumps)
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3e423213-24c7-4c74-aff4-35f00a7d60ec
---

`slot-backend` (code.hoelle.games/slot-backend/slot-backend) is a monorepo (root + packages/slot-backend, -core, -core-types, -types). Engines pin an exact published version (e.g. ax-mechanic-greed pinned `@hoelle/slot-backend@6.1.17`).

To fix a bug for a deployed version, do NOT use `main` — patch the matching **version branch**:
- Maintenance branches are named by version: `6.1.13`, `6.1.10`, `6.0.28`, ... created from the `vX.Y.Z` tag. If none exists for the version, create it from the tag.
- Patches bump the version as `X.Y.Z-N` (e.g. `6.1.13` → `6.1.13-1` → `-2`). Use `node scripts/set-version.cjs 6.1.17-1` (or `npm run version:set --`) — it updates all 5 package.json versions + internal `@hoelle/slot-backend*` dep pins.
- Land fixes via a `fix/<desc>-<version>` branch → MR **into the version branch** (not main).
- `package-lock.json`, `lib/`, and generated `version.ts` are gitignored.
- Build/lint: `npm run build` (workspace tsc), `npm run lint --workspace=packages/slot-backend`.

After publish, bump the consuming engine's pin to the new `X.Y.Z-N` and regenerate its lockfile with `npm install`.

See [[feedback_fold_into_open_mr]], [[feedback_glab_mr_flags]].
