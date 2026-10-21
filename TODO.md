# ToFScope status and next work

Status of the React/FastAPI application as of 2026-10-20. The frozen Marimo
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

## Next scientific features

- [ ] Depth calibration editor and physical-depth coordinates in views and exports.
- [ ] Peak identification, signal annotations, and explicit isotope measurements.
- [ ] Linked XZ/YZ cross-sections.
- [ ] Multi-signal 3D overlays and tiled views, including a depth profile alongside the volume.
- [ ] Persist and restore the new calibration, identification, and spatial-view state.

Implement these through the [replacement completion plan](docs/superpowers/plans/2026-10-18-react-fastapi-completion.md).
Depth calibration comes first because sections and 3D depend on its coordinates.
Original-resolution values must continue to drive profiles and exports.

## Qualification and project maintenance

- [ ] Complete TOFexplorer numerical round-trip checks on disposable files.
- [ ] Decide whether native TOFexplorer-channel export is needed beyond ToFScope saved copies.
- [ ] Qualify the target shared-storage deployment, including permissions, locking, and durability.
- [ ] Finish replacement feature-parity checks and release documentation.
- [ ] Review and merge the migration branch into `main` after GitHub CI passes.

The last local verification passed 167 Python tests, 44 browser workflows, and
independent wheel/sdist installation checks. Docker verification was blocked by
a stopped local daemon; shared NFS behavior remains unqualified. See the
[validation records](docs/validation/) and [roadmap index](docs/superpowers/plans/README.md).
