---
name: feedback-fold-into-open-mr
description: Fold follow-up fixes/changes into the current open MR instead of opening a new one
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fc318820-897c-470a-9719-8ecfd0153fc2
---

When a fix or small follow-up comes up while an MR is already open and unmerged
(e.g. on the hölle.games `hearth` repo), add it to that existing MR's branch
rather than spinning up a separate branch + MR. David pushed back hard when I
opened a standalone MR (!7) for a pipeline-refresh bug while MR !6 was still open
— he wanted it in !6.

**Why:** separate MRs for related in-flight work fragment review, create
merge-ordering/conflict friction (both touched the same file), and add overhead.

**How to apply:** if there's an open MR I (or we) am actively iterating on and the
new change is related or co-located, cherry-pick/commit onto that branch and push
to update the MR. Only open a new MR when the work is genuinely independent or the
other MR is already merged. When unsure which open MR, ask. See [[mr-reviewer]].

"Related" is broad: it includes **same-area product/feature changes, not just
bug fixes** — even when the new change feels like a conceptually distinct
decision. On the hizi-engine-creator buy-feature work I folded a redundant-file
cleanup into MR !143 but then opened a *separate* MR !144 for "remove the stake
boost mode" because it felt like a distinct product call. David: "I wanted it in
the same MR." Same subsystem + open MR ⇒ fold it (cherry-pick onto the branch,
update title/description to cover both, close the stray MR). Default to folding;
only split when the topics are unrelated.
