# ToFScope Explore

A read-only ToF-SIMS workspace built with React/TypeScript and FastAPI. One
installable Python application bundles the frontend and ECharts locally; one
service and port serve everything, with no runtime Node.js or CDN requirement.

```sh
uv sync --frozen
uv run tofscope --data-root /path/to/acquisitions
```

For an installed wheel: `pip install dist/tofscope-0.2.0-py3-none-any.whl`, then
`tofscope --data-root /path/to/acquisitions`. The launcher binds loopback and opens
the browser after readiness. `tofscope serve --no-browser` runs a service;
`tofscope open` opens its authenticated local UI; `tofscope doctor` checks
configuration/assets. See [deployment](docs/deployment.md) for configuration,
proxy authentication, resource limits, container use and restart behavior.

Open multiple files, including the same file repeatedly, in workspace tabs.
Each analysis owns independent named signals, ROI, frame coverage and viewing
choices. The **Signals** tray lists stored channels and raw integrations: choose
one with **Images** and show or hide additional **Profile** curves. Names and
colors stay with each signal when you switch views.

Use **Add stored signal** to search vendor channels, or **Create from spectrum**
to name a raw integration and draw/enter exact inclusive mass intervals. Multiple
intervals form a union. **Calculate signal** adds a result to the tray/profile;
**Show in images** switches the ion map and front projection explicitly. **Details**
exposes provenance, coverage, rename, duplicate, and custom **Edit signal** actions.
Edits stay separate until **Update signal** succeeds; progress, cancellation and
errors remain visible beside the signal. Failed calculations preserve old results.

**Calculate over frames** defines a signal's coverage. **Viewing depths** chooses
which available frames to show without recalculating the signal. **Analysis
settings** controls the profile/navigation range without rewriting recipes.
ROI and color controls live beside the image, relative scaling beside profiles,
and log Y beside the spectrum. Spectrum drag zooms normally and edits intervals
only while a signal editor is open. Images stay square; maximize/Escape and
Ctrl/Cmd-wheel zoom preserve the view. Ordinary wheel scrolls the page.

CSV exports visible ROI profiles at original scale and resolution. Schema-4
Settings JSON includes all committed signals and display choices. PNG includes
profile labels. Missing signal/SE coverage remains missing. Acquisitions stay
read only; pending drafts are never exported as committed results.

The pilot requires stored `PeakData` metadata; raw-only acquisitions are not yet
supported.

This is the **Explore pilot**, not full feature parity. Calibration editors,
atomic identification/isotope dialogs, sections, volume tools and controlled
native saves are specified in the [completion plan](docs/superpowers/plans/2026-10-18-react-fastapi-completion.md).
Acquisition writes and recipe import are unavailable. Workspace state is in
memory and lost on restart. Shared use requires a trusted authenticated proxy;
actual NFS deployment remains unqualified.

Scientific readers were compared before implementation: direct h5py preserves
selective bounded reads and exact existing NumPy integration without unused
signal-framework lifecycle machinery. See [reader evidence](docs/validation/reader-decision.md).
ECharts and Plotly passed the same focused interaction probes; ECharts was chosen
for the smaller bundle and public numerical-axis adapter. See
[renderer evidence](docs/validation/renderer-decision.md) and
[pilot qualification](docs/validation/pilot-qualification.md).

Build/verify from source (Node is needed only for frontend development/builds):

```sh
npm --prefix frontend ci
npm --prefix frontend run generate:api
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run test:e2e
uv run python scripts/build_frontend.py
uv run python -m unittest discover -s tests -v
uv build
uv run python scripts/check_distribution.py --artifacts dist --output /tmp/tofscope-distribution
uv run python scripts/check_container.py
```

Prebuilt assets are included in both wheel and sdist. A source build fails for
missing/stale assets. CI checks generated API drift, scientific/service tests,
frontend behavior, offline installed-package smoke and the container.

The complete Marimo prototype is frozen at
`37ecacf24c32388cd7f84bc11fa509989cc44775` in a separate checkout, with its own
locked environment. Recreate without changing this application:

```sh
git worktree add --detach /path/to/tofscope-prototype 37ecacf24c32388cd7f84bc11fa509989cc44775
cd /path/to/tofscope-prototype
uv sync --frozen
uv run marimo run app.py --headless --host 127.0.0.1 --port 27991
```

Set `TOFSCOPE_DATA_ROOT` and `TOF_FILE` there to inspect an acquisition. Keep
original acquisitions read only; prototype write flags should remain disabled.
The [baseline](docs/validation/prototype-baseline.md) records its test evidence.
Old widget assertions are preserved under `docs/validation/prototype-tests/`;
[coverage mapping](docs/validation/coverage-map.md) assigns them to replacement
checks or explicit completion-plan features. No legacy runtime or compatibility
adapter is shipped. The [migration design](docs/react-fastapi-migration.md) and
[pilot plan](docs/superpowers/plans/2026-10-18-react-fastapi-pilot.md) describe the
boundaries and decisions.
