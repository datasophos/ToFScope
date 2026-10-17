# ToFScope TODO

- [x] Multi-peak 3D mapping ([plan](docs/superpowers/plans/2026-10-16-01-multi-peak-3d.md)): support multiple tiled views and overlays with a separate colormap for each peak.
- [x] File browser for on-server files ([plan](docs/superpowers/plans/2026-10-16-02-server-file-browser.md)): configure the data storage location on the server and browse files within it.
- [ ] Write custom integration windows and their integrated data back into the HDF5 file ([plan](docs/superpowers/plans/2026-10-16-03-hdf5-write-back.md)).
  - Protected experimental save/reload is implemented; [commercial compatibility remains unverified](docs/hdf5-compatibility.md). Native additions currently require contiguous, full-acquisition windows.
- [x] Select multiple disjoint integration windows and combine them into one signal ([plan](docs/superpowers/plans/2026-10-16-04-disjoint-integration-windows.md)).
- [x] Peak identification helper and isotope abundance table ([plan](docs/superpowers/plans/2026-10-16-05-peak-identification-abundance.md)).
- [x] Calibrate profile depth by assigning known physical depths to selected frames and interpolating between those points ([plan](docs/superpowers/plans/2026-10-16-06-depth-calibration.md)).
  - Calibrated coordinates also apply to the front projection, XZ/YZ sections, and single/multi-ion 3D, with physical aspect ratios when X/Y dimensions are known.
- [x] modals are in the top left corner
- [x] Identify and depth calibration tools should be graphical first
- [ ] re-evaluate marimo as framework
  - [Platform and deployment recommendations](docs/platform-and-deployment.md) recorded; validate the proposed replacement with a packaged Explore screen before a full migration.
- [ ] Depth profile along side of 3D render

See the [roadmap index](docs/superpowers/plans/README.md) for dependencies, recommended order, and proposed decisions to review.
