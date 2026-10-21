# Repository Guidelines

## Project Structure

The Python application lives in `src/tofscope/`, organized into `api/`, `application/`, `presentation/`, `science/`, and `storage/`. The React/TypeScript client is in `frontend/src/`, grouped by app, calibration, explore, plots, and shared components. Python tests are in `tests/`; browser workflows and frontend tests are in `frontend/e2e/` and alongside frontend modules. Project documentation and validation records are in `docs/`. Packaged frontend assets are generated into `src/tofscope/static/`.

## Build, Test, and Run

- `npm --prefix frontend ci` installs locked frontend dependencies.
- `npm --prefix frontend run typecheck` checks TypeScript without emitting files.
- `npm --prefix frontend test` runs Vitest; `npm --prefix frontend run test:e2e` runs Playwright workflows.
- `uv run python -m unittest discover -s tests -v` runs Python tests.
- `uv run python scripts/build_frontend.py` builds the client and refreshes packaged static assets. For UI-only changes, refresh the browser to load the new hashed assets; a server restart is usually unnecessary.
- `uv run tofscope --data-root /path/to/acquisitions` starts the local app.

When a restart is necessary, restart the existing app process using its current port and data directory. Do not open another app tab or launch a duplicate service just to pick up UI changes.

## Style and Naming

Use four spaces for Python and two spaces for TypeScript/TSX. Keep Python modules and functions in `snake_case`; React components and component files use `PascalCase`; frontend utilities use `camelCase`. Name tests `test_*.py`, `*.test.ts`, or `*.spec.ts` according to the existing suite. Follow nearby formatting and typing patterns. Treat `src/tofscope/static/` as build output; edit `frontend/` sources and regenerate assets instead of changing bundled files by hand.

## Testing

Run the focused test closest to a change, then the relevant broader suite. Scientific changes should preserve original-resolution calculations and include numerical assertions. UI behavior changes should include frontend or browser coverage when practical. The README lists full source, distribution, and container checks.

## Commits and Pull Requests

Recent commits use concise imperative subjects, such as `Refine scientific plot controls` and `Fix portable browser artifacts`. Keep commits focused and describe the user-visible or scientific effect. Pull requests should summarize the change, link related issues when available, list verification commands and results, and include screenshots for visible UI changes.

## Configuration and Data Safety

Use `tofscope.example.toml` as the configuration reference; keep local paths and credentials out of commits. Treat acquisition files as read-only and use disposable copies for write or export validation.
