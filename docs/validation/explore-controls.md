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
load on refresh. Remote GitHub Actions were not checked.
