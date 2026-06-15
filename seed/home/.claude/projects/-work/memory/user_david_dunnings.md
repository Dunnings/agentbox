---
name: user-david-dunnings
description: "Who the user is — David Dunnings, dev on the Hizi slot engine at hölle.games"
metadata: 
  node_type: memory
  type: user
  originSessionId: bbb8bd6d-476c-4c33-960d-43cd10d07868
---

The user is **David Dunnings** (david.dunnings@hölle.games), a developer at the game studio **hölle.games**.

- Works on the **Hizi engine** ecosystem: the slot/casino game engine plus the **Hizi Engine Creator** (a Next.js + Rust/WASM tool for building, simulating, and balancing slot/plinko/etc. game outcomes). Repos live under `code.hoelle.games/hizi/*` (GitLab) and are cloned into `/work/hizi/`.
- Authored the `@hizi.io/engine-generator` npm package used by the creator.
- GitLab username on `code.hoelle.games`: `david.dunnings`.
- Technical and precise — comfortable with deep root-cause analysis (wasm-bindgen internals, brotli streaming, OPFS). Give him the mechanism and evidence, not just "fixed it." Prefers reproduction/measurement over speculation.
- **Tests/runs builds locally on Windows** (PowerShell; paths like `C:\Users\commi\...`), while the agent operates in a Linux container. So: give Windows/PowerShell-friendly local commands (`Remove-Item -Recurse -Force`, not `rm -rf`), and remember he must `git pull` pushed commits before local changes appear. When he reports "changes don't show," suspect the local side first — unpulled commits or dev-server/browser caching — before the code.

See [[mr-reviewer]] for his MR workflow preference.
