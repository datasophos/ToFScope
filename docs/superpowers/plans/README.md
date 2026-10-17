# ToFScope implementation roadmap

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
