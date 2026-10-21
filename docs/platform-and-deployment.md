> Implementation update (2026-10-18): the packaged React/FastAPI Explore pilot
> now replaces the Marimo application. Use [current deployment instructions](deployment.md)
> and [qualification evidence](validation/pilot-qualification.md). The prototype
> observations below are historical context, not current launch instructions.

# Platform and deployment recommendations

Recorded 2026-10-17. This is a proposed direction for the next stage, not an
implemented migration or an available installation interface. The current
prototype still runs with Marimo using the instructions in the main README.

## Recommendation

Develop toward a dedicated React + TypeScript frontend with a Python FastAPI
backend. Distribute the built frontend inside the Python package so users run
one application, served on one port. Support both a local workstation launcher
and a shared lab server deployment.

Ease of installation and maintenance is a primary requirement. Scientists and
small IT teams should not need to clone the repository, build JavaScript, or
assemble several services to use a release.

## Why reconsider Marimo

Marimo helped establish the scientific workflows quickly and remains useful
for demonstrations and experimentation. However, ToFScope now behaves like an
instrument workspace: linked plots, direct manipulation of selections,
maximized displays, graphical dialogs, multiple 3D layers, server file browsing,
and controlled HDF5 writes.

The current application uses a 29-line Marimo wrapper around an AnyWidget.
Most interface behavior is custom JavaScript, with an approximately 800-line
Python controller handling state and events. We use little of Marimo's notebook
reactivity or built-in interface. This assessment is based on the prototype's
architecture, rather than a claim that Marimo cannot support these features.

A dedicated frontend would give us explicit components and application state
for these workflows. It would not automatically resolve asynchronous races,
large-array performance, session isolation, or safe file access; those still
require deliberate implementation and testing.

| Option | Assessment for ToFScope |
| --- | --- |
| Continue with Marimo | Lowest immediate disruption; suitable for continued demonstrations. Less benefit as the permanent shell around an increasingly custom application. |
| Shiny for Python, Core | Credible if mostly Python development is the priority. Specialized plot interactions would still require custom JavaScript components. |
| React + TypeScript + FastAPI | Preferred direction for the graphical workspace. Adds developer build tooling and explicit responsibility for state, sessions, and computation. |
| Trame / VTK | Worth evaluating if advanced volume visualization becomes the dominant requirement. A larger change to the visualization approach. |

Panel is excluded from the proposed direction based on the user's preference.

## Deployment model

Build the frontend when publishing a release and bundle its assets with the
Python package. FastAPI can serve both those static files and the analysis API.
Node.js and npm would be developer/build dependencies, not user prerequisites.
Bundle the selected plotting libraries and other interface assets locally; runtime CDN access should not
be required. Keep computation and acquisition access on the machine running
Python.

| Mode | User experience | Operator responsibilities |
| --- | --- | --- |
| Local workstation | Launch ToFScope, open the browser automatically, and browse local or mounted acquisitions. | Install the package and its dependencies; configure an optional data root. Bind to localhost by default. |
| Shared lab server | Open a bookmarked URL and browse the configured server data directory. No client installation. | Run one Python service or container near the data, configure the POSIX/NFS mount and permissions, and provide HTTPS/access control as appropriate. |

For a lab with limited IT support and central acquisition storage, prefer the
shared server model. Large acquisition files remain near the computation;
browser clients receive plot and preview data. This does not eliminate the
server's memory, CPU, or storage requirements.

Offer a normal Python package as well as an optional versioned container image.
An illustrative future local installation interface is:

```sh
uv tool install tofscope
tofscope
```

These commands are a packaging target; this repository does not yet provide
that published package or launcher. A desktop installer could simplify local
installation further, but would require platform-specific builds, signing, and
release testing.

## Operational requirements

- One documented configuration file for the data root, bind address/port,
  write policy, and resource limits. Preserve compatible environment overrides
  where useful.
- One service and port for the initial deployment. No database or separate job
  service required initially; revisit if workload measurements justify them.
- A launcher with understandable startup errors and automatic browser opening
  for local use. Shared service mode must run without opening a browser.
- Versioned releases, reproducible dependencies, and documented upgrade and
  rollback procedures. Acquisition changes need their own backup/recovery
  policy; rolling back application code does not undo a data write.
- Useful logs, a health endpoint, and a diagnostic command for configuration,
  data access, and storage permissions.
- Explicit user-owned workspaces containing multiple independent open analyses,
  including multiple analyses of the same acquisition; analysis/user/global
  resource limits and fair computation scheduling.
- Explicit per-analysis state, bounded memory/computation, progress
  reporting, and handling of disconnects and obsolete requests. CPU-heavy
  analysis must not block the web event loop.
- Defined authentication and authorization for shared hosting, with an
  institutional HTTPS/login proxy where available. These are deployment work
  still to implement, not capabilities established by the current prototype.
- Writes disabled by default. Preserve the existing write validation, locking,
  backup, stale-session detection, and replacement protections.
- Validate locking and replacement behavior on the actual deployment mount
  before enabling NFS writes. Commercial ToF-Explorer compatibility remains
  unverified; a framework migration does not change that status.

Marimo also supports container deployment. Deployment simplicity by itself is
neither a reason to migrate nor a reason to retain it. Large datasets,
concurrent users, permissions, and safe writes remain responsibilities under
any framework.

## Replacement approach and acceptance

The [replacement proposal](react-fastapi-migration.md) expands this
direction into architecture boundaries, a packaged Explore-screen pilot,
scientific contracts, and acceptance milestones. The app is unreleased, so the
replacement may change structure and interfaces wholesale. Preserve Marimo in a
frozen reference checkout; no compatibility adapter or dual-runtime release is
required. This remains planning material; the replacement is not implemented.

1. Preserve the committed Marimo prototype in a runnable, frozen reference
   checkout before replacing the main application.
2. Build new application services and explicit session state, replacing the
   AnyWidget controller. Reorganize and reuse HDF5 handling, signal recipes,
   depth calibration, atomic identification, and write validation with their
   tests. No legacy transport or import compatibility is needed.
3. Compare Plotly.js and ECharts before implementing Explore, using the
   renderer evaluation in the replacement proposal. Prove linked selections,
   resizing/maximizing, asynchronous updates, and long computation behavior.
4. At the same time, produce an installable release containing the built
   frontend and a single launcher. Test installation outside the developer
   checkout, without Node.js or a frontend build step.
5. Demonstrate both localhost startup and a shared server configuration against
   a representative mounted data directory. Check isolation and resource use with two users each opening multiple analyses,
   including the same acquisition, before recommending shared operation.
6. Compare the replacement with the prototype before migrating the remaining
   dialogs and 3D tools. Adapt existing browser checks to protect behavior.

Treat the 3D renderer as a separate decision. Evaluate vtk.js alongside the
Plotly baseline, or Trame if remote rendering is needed, against concrete needs such as clipping planes, linked
orthogonal slices, larger volumes, and remote rendering. Replacing Marimo alone
will not improve volume rendering or reduce transferred array sizes.

## References

- [Marimo applications](https://docs.marimo.io/guides/apps/),
  [AnyWidget support](https://docs.marimo.io/api/inputs/anywidget/), and
  [container deployment](https://docs.marimo.io/guides/deploying/deploying_docker/).
- [Shiny custom components](https://shiny.posit.co/py/docs/custom-components-pkg.html).
- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/),
  [server operation](https://fastapi.tiangolo.com/deployment/manually/), and
  [WebSockets](https://fastapi.tiangolo.com/advanced/websockets/).
- [uv tool installation](https://docs.astral.sh/uv/guides/tools/).
- [Trame VTK local and remote rendering](https://github.com/Kitware/trame-vtk).
- [Current HDF5 compatibility and storage limitations](hdf5-compatibility.md).
