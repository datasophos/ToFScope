# Explore control and appearance validation

Validated on 2026-10-21 with Chrome on macOS, using disposable acquisition fixtures.

## Results

- `.venv/bin/python -m unittest discover -s tests -q`: 179 passed.
- `npm --prefix frontend test`: 22 passed across 7 files.
- `npm --prefix frontend run test:e2e`: 63 passed.
- `.venv/bin/python scripts/build_frontend.py`: TypeScript check and production build passed; packaged static assets refreshed.
- `git diff --check`: passed.

Browser coverage checks explicit viewing modes, committed versus draft range values,
plot-driven selection, equal toolbar heights at desktop width, narrow layouts,
profile CSV downloads, rounded maximized surfaces without resize handles,
calibration centering and anchor alignment, favicon delivery, and footer links.
Numerical coverage checks that viewing ranges preserve full-acquisition profiles
and original-resolution values while limiting CSV rows to the inclusive selection.

## Screenshots

- [Frame range controls](explore-controls/frame-range.png)
- [Centered calibration editor](explore-controls/calibration-editor.png)
- [Rounded maximized spectrum](explore-controls/maximized-spectrum.png)

## Deployment

The separate analysis-range field and command are removed, including from saved
analysis documents and the generated API. Files saved with the retired range field
are intentionally unsupported; no migration is provided for this unreleased app.
Signal calculation coverage and saved viewing selections remain supported.

Restart the application to load the Python changes. The current development service
was left running to preserve its in-memory login and open analyses. Rebuilt UI assets
load on refresh. Remote GitHub Actions were not checked during the original UI validation.

## Help-test CI timeout follow-up (2026-10-21)

The user-reported [CI run](https://github.com/datasophos/ToFScope/actions/runs/39628449540)
failed at the monolithic help test's 30-second limit. Its logs did not identify a
stalled action, and the run uploaded no diagnostic artifacts. The timeout did
not reproduce in 20 local probes using CPU throttling, including a smaller
viewport and different font metrics; its underlying cause remains unconfirmed.

The same coverage now runs as four isolated scenarios: hover/discoverability,
keyboard/pinned dismissal, maximized Escape behavior, and SE-specific content.
Each action has a 10-second limit within the unchanged 30-second test budget.
Playwright retains traces and screenshots on failure; CI uploads test-results
for seven days so future failures retain their action log and page context.
No application behavior, retries, or overall test timeout was changed.

Follow-up verification:

- `npm --prefix frontend run test:e2e -- help.spec.ts --repeat-each=10`: 40 passed.
- `npm --prefix frontend run test:e2e`: 66 passed.
- `npm --prefix frontend run typecheck`: passed.
- `npm --prefix frontend test`: 22 passed.
- Workflow YAML parsed; PR/main triggers and the conditional artifact step checked.
- `git diff --check`: passed.

No subsequent CI run was monitored.

## Confirmed plot-heading overlap fix (2026-10-21)

The next [user-reported CI run](https://github.com/datasophos/ToFScope/actions/runs/39630029843)
provided the retained screenshot and action log: ROI intercepted clicks on SE
Image help. `.plot-heading` used `min-width: 0`, allowing its nested title/help
group to overflow beneath the adjacent toolbar. Linux font metrics made the
problem visible at the default CI viewport.

A regression with 20 px plot headings reproduced the obstruction locally before
the fix. It checks hit testing and normal pointer clicks for all four plot help
buttons after selecting SE display. Changing the heading minimum width to
`min-content` reserves enough space; the existing flex wrapping moves the controls
to another row when needed. No forced clicks, retries, or longer timeouts are used.

Evidence:

- [CI screenshot showing ROI over the help button](explore-controls/ci-se-help-overlap.png).
- [Fixed layout with larger headings](explore-controls/heading-help-layout.png).
- New regression failed before the CSS change and passed after it.
- `npm --prefix frontend run test:e2e -- help.spec.ts`: 5 passed.
- `npm --prefix frontend run test:e2e`: 67 passed.
- `npm --prefix frontend test`: 22 passed.
- `.venv/bin/python scripts/build_frontend.py`: TypeScript check and production build passed.
- Packaged frontend source hash matches current sources; `git diff --check` passed.

This supersedes the earlier uncertainty about the CI help timeout. No subsequent
CI run was monitored.
