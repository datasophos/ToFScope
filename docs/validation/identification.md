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

## Identification dialog refinement

Manual testing on the local example datasets exposed a spectrum-scale bug:
`PlotPanel` enabled logarithmic scaling only for the main spectrum's internal
name. An explicit spectrum-scale property now enables the same log/linear
behavior in the identification dialog, with log selected initially and its
setting independent from Explore. Shared plot margins, controls and scientific
intensities remain unchanged.

The dialog now uses stacked field labels, visible white input/select fields,
aligned search controls, separated annotation/integration groups and a compact
spectrum. Desktop and narrow-screen checks cover field spacing, containment and
independent scale toggling.

Candidate matching still uses the exact server tolerance and includes the full
catalog. Presentation defaults to isotopes with a tabulated positive natural
abundance and sorts by abundance, then absolute mass error. Ranged abundances use
the interval midpoint only for ordering; the table preserves the interval and
shows percentages. Closest m/z ordering and inclusion of entries without natural
abundance remain explicit options. Natural abundance is relative to isotopes of
the same element, so the interface does not label this ordering an identification
probability or sample composition. The bundled catalog includes 3,352 masses but
only 288 with reference natural abundances; many other entries describe
radioactive or synthetic isotopes rather than missing acquisition measurements.

At the reported 47.95924758911 Th position with 0.1 Th tolerance and charge +1,
Ti-48 (73.72%) precedes Ca-48 (0.187%). The optional unlisted-abundance view retains
K-48 and other catalog entries. At 0.01 Th tolerance Ti-48 is correctly excluded;
the ranking never expands the user's matching window.

Refinement validation: TypeScript and the rebuilt packaged frontend passed;
26 frontend tests and all 70 browser workflows passed. The three identification
browser workflows also passed after restoring ten significant digits in the
predicted-mass display. An independent review found no remaining functional
issues. The existing port-8765 service remains running with the user-confirmed
local dataset directory; its health/readiness and rebuilt static asset hashes
were verified without restarting it or opening another tab. The directory is
recorded in private persistent agent memory, outside git.

[Refined dialog and Ti-48 ordering](identification/identification-natural-abundance.png).

The measured-mass field shows four decimal places while unfocused and exposes
its full exact value on focus (also in its title), using the existing signal
editor's focus/select pattern. Search and assignment still use the unrounded
value. The tolerance spinner changes by 0.1; manual tolerances such as 0.01 remain
accepted. Browser checks exercise ArrowUp/ArrowDown, compact/exact focus changes,
and the actual unrounded candidate request. All three identification workflows,
26 frontend tests, TypeScript and the packaged build passed after these changes.

## Automatic search on spectrum picks

Clicking the identification spectrum now picks/snaps the mass and immediately
queries candidates using that exact new m/z and the current tolerance, unit and
charges. The search receives the picked value explicitly rather than reading
React state from the previous render. Manual entry retains the Find candidates
button. Opening the dialog does not trigger a search.

Request serial checks protect result, error and busy-state updates; changing
inputs or closing the dialog invalidates older searches. A browser regression
holds the first response, clicks another mass, verifies current settings/new
mass in both requests, then releases the old response and confirms the second
candidate set remains displayed. Seven focused browser workflows, 30 frontend
tests, TypeScript and the packaged build passed. Independent review was clean.


Tolerance defaults to 0.3 Th. Editing tolerance, switching Th/ppm, or checking
or unchecking a charge immediately searches using the new setting and current
mass. Clearing the tolerance invalidates results until a value is entered.
The settings regression verifies real request payloads for each control,
including negative polarity and charge removal, and checks that changing to a
narrow ppm tolerance removes the previous candidate results.
