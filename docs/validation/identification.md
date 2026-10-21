# Atomic identification and isotope measurements

Task 2 qualification, 2026-10-21. Atomic candidates use the bundled NIST/CIAAW
catalog and signed electron-mass convention, with explicit ±1–3 charge selection,
Th/ppm tolerance, uncertainty and catalog provenance. No runtime download occurs.
Queries exceeding 256 matches or the configured response budget are rejected
without truncating the candidate set; narrow tolerance/charge selection to retry.

The identification dialog provides its own zoomable spectrum. Picking snaps to a
local maximum within seven display pixels; exact m/z input remains available.
The main Explore spectrum retains its existing click/drag/zoom semantics.
Annotate changes metadata on a stable signal ID without changing its name,
original vendor label or scientific recipe. Apply window opens an exact custom
draft. Add comparison explicitly submits the existing bounded integration job,
with its assignment captured atomically.

Measurements run explicitly through the owner-scoped job lifecycle and cache.
The scientific routine reads one original-resolution volume lease at a time,
sums the captured ROI on common covered frames using float64 accumulation, and
retains missing coverage and overlap statuses. No display log or relative scaling
enters calculations. Overlapping windows suppress every selected-set fraction;
unknown reference abundance remains null. Results are signal ratios, not
quantitative composition. Captured names, assignments, mass windows, requested and
actual coverage, dataset generation and catalog provenance remain exportable.

ROI, viewing-frame, signal recipe or assignment changes mark captured results out
of date. Display scaling and calibration-unit changes do not. Older results stay
visible until another explicit measurement succeeds. New measurements supersede
older pending results; cancellation, analysis closure and source replacement
prevent obsolete publication. Current measurement job receipts survive history
pruning. Candidate and measurement responses reserve transport admission until
sending completes.

Settings JSON and isotope CSV preserve measured m/z, signed Th/ppm errors,
reference uncertainty, source IDs and checksum/retrieval metadata. Saved HDF5
analysis documents now use schema 3 to preserve annotations and measurements.
Versions 1/2 still load; older applications reject schema 3. Reopening creates
fresh service/signal/recipe identities and remaps the measurement references.
The measurement's original source generation remains provenance. Saved current
measurements must agree with stored scope/recipes/assignments; nonfinite values
and inconsistent atomic assignments are rejected. Stale measurements retain
that status across save/reopen. Repeated saves remain supported.

## Verification

- Python: `python -m unittest discover -s tests -v` — 194 tests passed.
- Frontend: `npm --prefix frontend test` — 23 tests passed.
- TypeScript: `npm --prefix frontend run typecheck` — passed.
- Browser: `npm --prefix frontend run test:e2e` — 69 workflows passed;
  the final explicit selector-label regression also passed in the two focused
  identification workflows.
- API: regenerated OpenAPI and TypeScript contracts.
- Frontend: rebuilt packaged hashed assets with `scripts/build_frontend.py`.

Focused coverage includes Ti-48's nonzero measured mass error and 0.0003
reference-abundance uncertainty, Al-27 annotation with preserved labels,
unknown C-14 abundance, original sums 75/15 and ROI sums 39/9, partial/absent
common coverage, overlap suppression, exact raw integration sum 3, owner denial,
retry idempotency, invalid metadata, fresh-ID save/reopen and repeated save,
response admission, bounded broad queries, 260-job history pruning and
superseded-reader cancellation. Existing isotope/abundance numerical tests
retain independent charge, ppm, natural-range and zero-total assertions.

The wheel and sdist were independently installed and exercised with
`scripts/check_distribution.py --artifacts dist --output /tmp/tofscope-identification-distribution`.
Both passed with no Node, no runtime external requests, and no prototype/scientific
UI runtime dependencies. Added checks identify H-2, annotate a calculated signal,
measure an exact sum of 3, save, restart, remove the original acquisition, and
restore the assignment and measurement from the saved copy. Existing exact CSV,
calibration, colormap and interrupted-download checks also passed. The artifacts
were rebuilt after the final changes. Remote CI was not checked.

Screenshots: [atomic identification](identification/atomic-identification.png),
[isotope measurements](identification/isotope-measurements.png).
