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

Execution rulings: backend contract tasks 1–3 were coordinated (intermediate
checkouts not releasable); initial image preparation moved into Task 1 to match
its replacement snapshot; assets were staged until matching backend activation
(source/asset hashes checked to prevent drift); this review starts at this plan's
base because the earlier pilot was already reviewed. The isolated implementation
branch is retained; no merge, publication or external deployment is performed.
