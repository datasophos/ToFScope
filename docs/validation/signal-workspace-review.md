# Signal workspace final review

A fresh reviewer inspected `7703c6a..6a576a5` against the approved spec, plan and
qualification evidence. The first model hit a usage limit before reviewing;
a fresh GPT-6.1 reviewer completed the read-only review. It did not independently
rerun the executor's numerical/performance/package checks.

Three Important issues were reproduced and fixed with failing-then-passing tests:

- A stale open draft used the latest polled recipe version and could overwrite
  another view's completed edit. Drafts now retain their opening recipe/name
  versions and reject conflicts while retaining input. Server recipe checks and
  revision envelopes still protect the submission race.
- Removing queued signals did not promptly release job admission slots. Removal
  now cancels their queued/running jobs and drops obsolete generation tokens.
- Pruning old terminal jobs removed records still referenced by retained signals,
  which could block polling after reattachment. Referenced jobs are protected by
  the bounded signal collection; 256 additional terminal records are retained.
  Superseding/removing/closing signals releases that protection. A 260-update
  regression verifies both retention and eventual pruning.

The reviewer graded stored-duplicate coverage as Minor. The executor regraded it
Important: duplication should preserve scientific coverage. The browser regression
failed with full-range duplication and passes when the exact source coverage is
sent and validated. All four fixes are one review fix pass.

After the fixes: 111 Python tests, 11 frontend unit tests, 23 browser tests and
TypeScript checking pass. Packaging is rebuilt and its installed smoke rerun after
the fixes. Scientific arithmetic/readers are unchanged; the full-volume equality
and real-data timing evidence remains explicitly scoped to the preceding
qualification run.

Deferred minor: stored-channel deduplication restores profile visibility but does
not focus/scroll the already existing tray row. It does not create another signal.

The reviewer declined independent judgment of numerical equivalence, timings,
wheel/sdist offline behavior, hardware/NFS, manual screen-reader usability and
pre-existing issues outside the redesign. Executor-run qualification supplies the
first three; hardware/NFS and manual screen-reader checks remain unverified.
The earlier pilot had a separate review/qualification. These distinctions do not
turn unavailable external checks into passes.

## Execution rulings

- Task 1: in progress. Ruling: backend contract tasks 1–3 are a coordinated replacement; focused tests gate commits, whole backend suite restored in Task 3, as plan specifies. Cost if wrong: interim checkout is not releasable.

- Task 1: Ruling: move build_services.prepare migration from Task 3 to Task 1 — initialization must load image_signal.recipe to run the specified invalidation test; no compatibility fields added. Cost if wrong: one initialization dependency moved earlier.

- Task 7: Ruling: build bundled assets/package in /private/tmp/tofscope-signal-package before activating source static assets — the live process still has the old Python contract and serving the new frontend early would break its workspace. Copy verified assets into the implementation checkout only when ready for restart. Cost if wrong: staged/canonical source drift; compare source/asset hashes before activation.

- Task 7: Ruling: final review uses plan-start 7703c6a as review base — earlier pilot already independently qualified and this plan changes its signal workflow; reviewer sees whole redesign and affected source. Cost if wrong: unrelated pre-existing pilot issues are outside this review range.

- Final: Ruling: stored duplicate coverage was graded Minor by reviewer, regraded Important — explicit duplication must preserve scientific coverage, so it joins the fix pass. Cost if wrong: one optional frames field and regression.

- Final: Ruling: declined numerical/performance/offline judgments are covered by executor-run qualification, not independently rerun by reviewer; hardware/NFS/manual screen-reader validation remain unverified and prior pilot outside this diff was already qualified. Cost if wrong: local tests may miss environment/accessibility issues; no claim of those unavailable checks passing.

- Final: Ruling: retain isolated implementation branch/worktree — user explicitly requested isolated execution and no external deployment; no merge/push/release was requested. Cost if wrong: integration into main remains a separate user decision.
