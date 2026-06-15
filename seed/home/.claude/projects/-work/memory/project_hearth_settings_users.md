---
name: project_hearth_settings_users
description: "Hearth Settings page = self profile + admin user management; avatars are colour-only, role/admin admin-only"
metadata: 
  node_type: memory
  type: project
  originSessionId: fc318820-897c-470a-9719-8ecfd0153fc2
---

Hearth's **Settings** page (MR !25) is the home for user/profile management.

Decisions (product calls, not obvious from code):
- **Avatars are colour-only.** Users pick an avatar colour from a fixed palette
  (`AVATAR_COLORS` in `web/src/api.ts`); **initials are always auto-derived as
  First+Last** (`deriveInitials` in `server/users.mjs`) and never edited. Real
  photo upload was explicitly deferred — it would need Cloudflare R2 wired into
  the Worker.
- **Self-service is limited to title + avatar colour + own password.** A
  non-admin editing themselves can ONLY change title/colour; the staff/client
  **role** and the **admin** flag are admin-only (changing your own role would
  be privilege escalation — a client could unlock internal content). "Change
  your role" from the user meant job *title*, not the security role.
- **Admins** get full People management: add/edit staff + client contacts, set
  role/org/admin, reset passwords, remove. Guards: can't remove your own admin
  or delete your own account; deleting a user is refused if they're tied to any
  content ([[project_hearth_comment_ids]]-style ref checks via countUserRefs).

No schema change was needed — the `users` table already had every column.
Endpoints: POST/PATCH/DELETE `/api/users`, POST `/api/users/:id/password`.
