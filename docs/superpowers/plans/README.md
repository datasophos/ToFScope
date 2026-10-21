# ToFScope implementation roadmap

## React/FastAPI replacement — 2026-10-18

The unreleased app may be replaced wholesale; the Marimo prototype is preserved
in a frozen reference checkout. These plans implement the
[replacement proposal](../../react-fastapi-migration.md):

1. [Packaged Explore application and multi-user foundation](2026-10-18-react-fastapi-pilot.md):
   scientific reference, package boundaries, independent analyses, resource/job
   management, renderer evaluation, API, React Explore, distribution and deployment.
2. [Complete workspace](2026-10-18-react-fastapi-completion.md): depth calibration,
   identification/isotopes, sections, spatial renderer selection, multi-layer 3D,
   controlled saves and full parity qualification.

The packaged Explore application is implemented and qualified. Its follow-up
[signal workspace](2026-10-19-explore-signal-workspace.md),
[file-centered persistence](2026-10-19-file-centered-analysis.md), and
[raw preparation](2026-10-20-raw-acquisition-preparation.md) plans are also
implemented. Depth calibration is implemented and merged through
[PR #2](https://github.com/datasophos/ToFScope/pull/2); the subsequent Explore
control/layout fixes and CI cleanup are merged through
[PR #3](https://github.com/datasophos/ToFScope/pull/3). The completion plan's
remaining scientific backlog starts with identification/isotopes, followed by
sections and 3D. Controlled native vendor
exports remain separate from the supported Save as workflow, which creates new
HDF5 copies and restores analysis state.

[TODO.md](../../../TODO.md) tracks current replacement capabilities. The older
plans below describe prototype work and remain historical context; completed
prototype features do not imply replacement UI parity.

## Prototype roadmap — 2026-10-16

These are proposed implementation plans for the six items in [TODO.md](../../../TODO.md), grounded in the current Python/AnyWidget/Plotly prototype. No feature implementation or HDF5 mutation is part of this planning change.

Read the [shared design brief](../specs/2026-10-16-roadmap-design.md) first. Each plan includes file boundaries, concrete interfaces, test-first tasks, validation commands, acceptance criteria and proposed commit boundaries.

| TODO item | Plan | Dependencies |
| --- | --- | --- |
| 1 | [Multi-peak 3D tiles and overlays](2026-10-16-01-multi-peak-3d.md) | Signal recipes from item 4 |
| 2 | [Configured server file browser](2026-10-16-02-server-file-browser.md) | None |
| 3 | [HDF5 integration write-back](2026-10-16-03-hdf5-write-back.md) | Items 2 and 4; optional depth metadata from 6 |
| 4 | [Multiple disjoint integration windows](2026-10-16-04-disjoint-integration-windows.md) | None; establishes shared signal recipes |
| 5 | [Peak identification and abundance table](2026-10-16-05-peak-identification-abundance.md) | Signal recipes from item 4 |
| 6 | [Known-depth calibration](2026-10-16-06-depth-calibration.md) | None; interoperates with recipe/persistence work |

## Recommended implementation order

1. **Disjoint windows**: settle signal definitions once, before adding more consumers.
2. **File browser/configuration**: establish the server data root and read/write policy.
3. **Depth calibration**: deliver a contained scientific navigation improvement.
4. **Identification/abundance**: build on the common integration definitions.
5. **Multi-peak 3D**: reuse recipes and benchmark layered previews on the client browser.
6. **Write-back**: persist the settled recipes and calibration after the read-only workflows are established.

The order can change: items 2 and 6 are independent, and item 1 can precede item 5. Avoid implementing overlapping changes to `workspace.py`/`web/workspace.js` concurrently without integration coordination.

## Decisions worth reviewing before execution

- Does write-back need to appear in commercial ToF-Explorer immediately, or is a ToFScope-readable HDF5 extension acceptable first? The supplied file's native peak datasets are fixed-size, so a native append requires rebuilding datasets and compatibility testing.
- Is the initial identification scope of atomic ions sufficient, before molecular ions/adducts?
- Is interpolation only between depth anchors sufficient, with unknown depths outside the calibrated span?
- Does the proposed total 500,000-voxel preview budget perform adequately on the client browser?
- What storage filesystem will host writable acquisitions, and which other processes may open them?

These choices are recorded as proposals so the plans can be reviewed without mistaking them for confirmed client requirements. Execution is not started automatically.

## Confirmed requirements — 2026-10-17

- Execution continues in the recommended order; disjoint windows are complete.
- Storage is a POSIX filesystem such as an NFS mount, configured on the server.
- Depth calibration includes a fixed anchor at frame 0 / depth 0; interpolate
  between known anchors and leave later uncalibrated depths unknown.
- Atomic isotope ions suffice for the initial identification helper.
- Write-back must expose new channels to commercial ToF-Explorer. A namespaced
  extension alone is insufficient; native schema export and a commercial
  round-trip are acceptance requirements. Test on disposable copies first.
