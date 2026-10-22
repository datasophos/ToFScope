# ToFScope status and next work

Status of the React/FastAPI application as of 2026-10-21. The frozen Marimo
prototype is preserved at tag `prototype-2026-10-18`; its completed features are
reference behavior, not evidence that the replacement exposes those features.

## Available

- [x] Packaged React/FastAPI Explore application with bundled frontend assets.
- [x] Server file browser, independent file tabs, and configurable acquisition/saved-copy folders.
- [x] Named signals, multiple disjoint integration intervals, image selection, and profile comparisons.
- [x] Ion/SE maps, front projections, depth profiles, mass spectra, linked selections, and exports.
- [x] Save analysis state and full-resolution custom results in a new HDF5 copy; restore by reopening it.
- [x] Confirmed raw acquisition preparation, including explicit missing-metadata assumptions.
- [x] Compact prepared files with channel-oriented gzip storage and verified numerical preservation.
- [x] Graphical depth calibration with exact anchors, partial physical-depth profiles/front projections, nm/µm/mm display, and physical-depth CSV exports.
- [x] Persist/restore calibration and coordinate/unit choices in HDF5 copies.
- [x] Explicit All frames, Single frame, and Frame range viewing modes, with independent axis units and full-acquisition profiles.

## Next scientific features

- [x] Peak identification, signal annotations, and explicit isotope measurements.
- [ ] Linked XZ/YZ cross-sections.
- [ ] Multi-signal 3D overlays and tiled views, including a depth profile alongside the volume.
- [x] Persist and restore identification annotations and captured isotope measurements.
- [ ] Persist and restore future spatial-view state.

Implement these through the [replacement completion plan](docs/superpowers/plans/2026-10-18-react-fastapi-completion.md).
Depth calibration is available as the coordinate foundation for sections and 3D.
Linked XZ/YZ cross-sections are the next unfinished task.
Original-resolution values must continue to drive profiles and exports.

## Qualification and project maintenance

- [ ] Undo functionality would be nice
- [ ] Complete TOFexplorer numerical round-trip checks on disposable files.
- [ ] Decide whether native TOFexplorer-channel export is needed beyond ToFScope saved copies.
- [ ] Qualify the target shared-storage deployment, including permissions, locking, and durability.
- [ ] Finish replacement feature-parity checks and release documentation.
- [x] Merge the packaged Explore migration and depth calibration into `main` ([PR #1](https://github.com/datasophos/ToFScope/pull/1), [PR #2](https://github.com/datasophos/ToFScope/pull/2)).
- [x] Merge Explore control/layout fixes, branding, and CI cleanup ([PR #3](https://github.com/datasophos/ToFScope/pull/3)).

Recorded local validation includes 194 Python tests, 30 frontend unit tests,
and the latest 71 browser workflows, plus TypeScript checks and a rebuilt client.
See [identification qualification](docs/validation/identification.md) for atomic
matching, measurements and save/reopen evidence. See [Explore control validation](docs/validation/explore-controls.md) for the
confirmed help-button overlap fix and [depth qualification](docs/validation/depth-calibration.md)
for calibration and independent wheel/sdist installation evidence. Shared-storage
deployment and commercial numerical round trips remain unqualified.

The separate analysis range has been removed. Profiles use the full acquisition
and each signal retains its own calculation coverage. Saved files containing the
retired analysis-range field are intentionally unsupported; no migration is planned
for this unreleased application.
