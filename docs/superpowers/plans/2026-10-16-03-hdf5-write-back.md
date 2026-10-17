# HDF5 Integration Write-Back Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Implementation requires a separate user instruction; this plan is a proposed design.

**Goal:** Save custom integration recipes and data into the selected acquisition HDF5 file and reopen them.

**Architecture:** First add an additive ToFScope extension group, preserving vendor datasets. Publish changes through a locked, backed-up, verified temporary copy followed by replacement at the original path; treat native PeakData compatibility as a separate measured milestone.

**Tech Stack:** h5py, NumPy, filelock, pathlib/shutil/os, existing signal/config interfaces, unittest, Playwright

**Spec:** [Roadmap design brief, section 3](../specs/2026-10-16-roadmap-design.md).

## Global Constraints

- Keep Marimo + AnyWidget + Plotly; do not introduce Panel.
- Treat frame limits as zero-based and inclusive.
- Do not change source HDF5 files except through explicit write-back.
- Preserve existing shared ROI, All depths, maximize/restore, and offline operation.
- Scientific transforms must not silently change analysis intensities.

## Dependencies and file boundaries

Requires the disjoint-window recipe/reader plan and the server file-browser/config plan. Optional depth metadata uses the calibration plan when available. Create `integration_store.py` for extension schema/readers, `dataset_io.py` for cooperative file locks/identity/replacement, and `web/save_integration.js` for explicit Save UI. Add `filelock` to `pyproject.toml` and regenerate `uv.lock` during implementation, not during this planning task.

The inspected example has fixed-size PeakData and PeakTable datasets. Simply resizing either to append a native channel is not a viable implementation. The first deliverable is discoverable by ToFScope, with vendor-reader visibility explicitly unproven.

## Review Focus

- A failed/cancelled write before replacement must preserve the original file and all vendor data (Task 2).
- Concurrent writes, external modification and stale open sessions must not overwrite each other silently (Tasks 2, 3).
- Partial-frame data must retain coverage rather than zero-padding unmeasured frames (Task 1).
- Fixed PeakData shapes, external links and unsupported filesystem semantics must not trigger an unsafe fallback (Tasks 1, 2, 4).
- A disjoint recipe cannot be exported as one native bounding interval without changing its scientific meaning (Task 4).

### Task 1: Define and round-trip an additive extension schema

**Files:** Create `integration_store.py`, `tests/test_integration_store.py`; modify `signals.py`, `explorer.py`.

**Interfaces:** `write_integration_group(h5: h5py.File, record: IntegrationRecord, frame_data: Iterable[np.ndarray]) -> str`; `list_saved_integrations(path) -> list[SavedIntegrationInfo]`; `read_saved_integration(path, saved_id: str) -> np.ndarray`. `IntegrationRecord` includes UUID, schema version 1, derivation `SignalRecipe`, source-file generation/normalization metadata, creation UTC, app version, full spatial shape, inclusive frame coverage and optional calibration metadata.

- [ ] Write tests using temporary synthetic HDF5: save/reopen one and two-interval signals; recipe and values must round-trip exactly; a record covering frames 10–12 has three layers and declares that coverage. Preserve original PeakTable/PeakData shapes, attributes and values.
- [ ] Test duplicate/malformed UUID rejection (including slashes, absolute HDF5 paths and `..`), Unicode labels, incomplete group rejection, unsupported schema versions and wrong shape/frame counts. User labels are metadata, not HDF5 path names. Finish a valid group with `complete=true`; readers ignore incomplete records.
- [ ] Run `uv run python -m unittest discover -s tests -p 'test_integration_store.py' -v`; verify failure, then implement `/ToFScope/Integrations/<uuid>/{recipe_json,data}` with versioned attributes, frame-chunked lossless data, shape validation and finite-value checks. Writer receives full-XY scientific values, not ROI-cropped/logged/downsampled display data.
- [ ] Add saved-record discovery as a separate list and `read_signal` saved-reference dispatch. Retain the original derivation recipe inside record metadata. Add a source-generation ID so caches can distinguish replacements; do not replace existing vendor fields.
- [ ] Run round-trip tests. Commit: `Persist custom integrations in a versioned HDF5 extension.`

### Task 2: Publish writes with backup, identity checks and a shared lock

**Files:** Create `dataset_io.py`, `tests/test_dataset_writeback.py`; modify `integration_store.py`, `explorer.py`, `server_config.py`, `pyproject.toml`, `uv.lock`.

**Interfaces:** `file_identity(path) -> FileIdentity` includes resolved path, device/inode where available, size, mtime_ns and ToFScope generation; `dataset_lock(path, timeout: float=0)` returns the same process-local, reentrant lock object for each canonical path and provides cross-process filelock exclusion to all ToFScope file operations; `save_to_acquisition(settings, relative_path, record, frame_data_factory, expected_identity) -> SaveResult`. `frame_data_factory()` is repeatable for verification/retry and does not hold an open handle across replacement.

- [ ] Write fault-injection tests at backup, copy, HDF5 write, verification and final identity-check stages. The original must remain byte-identical on every pre-replacement failure; a failure after successful replacement must report saved/reload-required rather than invite an unsafe blind retry. The backup is retained and failures identify any recoverable temporary file. Add insufficient-space and disabled-write-policy tests.
- [ ] Test two processes contending for the same lock, file modification after reconstruction, stale source identity (including a source change before Save preview), nested read-under-write lock reentrancy, permissions failure and paths outside the configured root. Test all reads/writes use the cooperative lock for a replacement; do not disable HDF5 locking.
- [ ] Run `uv run python -m unittest discover -s tests -p 'test_dataset_writeback.py' -v`; verify failure, then add filelock and implement backup + sibling temporary copy, permission preservation, root revalidation, free-space check (two source sizes plus projected result), write/close/reopen verification, source recheck and same-filesystem `os.replace`.
- [ ] Close every h5py handle before replacement, clear `_stored_peak`/`_se_mean` and saved-record caches after success, and return a new generation. Refuse unsupported external-link/layout situations until verified; cloud/network filesystems require a documented locking/replacement probe on the actual server before write enablement. No guarantee is claimed for non-cooperating vendor/acquisition writers.
- [ ] Run all store/write tests on disposable files; inspect the preserved vendor tree before/after. Commit: `Publish HDF5 additions through verified backup and replacement.`

### Task 3: Add explicit Save and reload/stale-session handling

**Files:** Create `web/save_integration.js`, `scripts/check_writeback.py`; modify `workspace.py`, `web/workspace.js`, `web/workspace.css`, `README.md`.

**Interfaces:** `save_preview {recipe_id}` returns target, intervals, frame coverage, size estimate, disk requirement and expected file identity without mutation. `save_integration {recipe_id,label,expected_identity}` is an explicit action, policy checked on the server. The identity is captured with the loaded/reconstructed volume, not freshly substituted at Save preview time; stale prepared values are rejected. Result includes saved UUID/new generation; affected controllers detect old generations and require reload before additional saves.

- [ ] Write a failing browser scenario against a disposable acquisition copy with writes enabled: construct a custom window, review the exact target/recipe, save, reload, select the saved record and compare its map/profile to pre-save values. Verify the acquisition path is unchanged and vendor peak rows remain unchanged.
- [ ] Test disabled writes, Cancel, stale identity, insufficient disk, two open sessions and partial-frame records. A stale session must not save old data over a newer file; show Reload acquisition and preserve its analysis recipe for reapplication.
- [ ] Implement Save integration with a concise target/coverage summary and progress. Update the current session after successful reload; other sessions detect generation mismatch on the next file operation and mark themselves stale. Never save because a user changes a numeric bound or downloads a recipe.
- [ ] Run `uv run python scripts/check_writeback.py` using only fixture files, all persistence tests and existing comparison checks. Document storage overhead, backups, lock scope and the ToFScope-only extension visibility.
- [ ] Commit: `Save and reopen custom integrations from the workspace.`

### Task 4: Establish native PeakData compatibility separately

**Files:** Create `docs/hdf5-compatibility.md`, `tests/test_vendor_export.py`; create `vendor_export.py` only if the validation gate passes. Test dependencies belong in the dev dependency group and are pinned at implementation time.

**Interfaces:** Proposed `export_native_copy(source_path, destination_path, recipes) -> Path`; output is a new file, not an in-place replacement of the acquisition's fixed arrays. Only contiguous, full-acquisition signals are eligible initially; reject disjoint or partial signals explicitly.

- [ ] Inventory reader/vendor-required peak counts, normalization, labels, table dtype, axis order, compression, external links and acquisition metadata from representative files and current RosettaSciIO/eXSpy readers. Write executable round-trip fixtures before changing native structures.
- [ ] Verify whether the commercial software reads the namespaced extension; record observed behavior rather than assuming it. Ask for a vendor-software validation run if that tool is unavailable; native compatibility remains unverified until then, while Tasks 1–3 remain independently shippable.
- [ ] If supported, implement a new native-compatible output copy by streaming old channels plus new contiguous channels into newly created larger datasets and rebuilding the peak table/counters together. Preserve unknown groups/attributes; do not load the entire 17.2-GiB expanded cube. Refuse unsupported schemas and semantic shortcuts.
- [ ] Run `uv run python -m unittest discover -s tests -p 'test_vendor_export.py' -v` with supported external readers; compare original channels and new derived data. Validate the output in commercial software before documenting vendor support.
- [ ] Commit the compatibility report and, only if proven, exporter: `Document and validate native peak export compatibility.`

## Acceptance

Tasks 1–3 save full-resolution custom data and exact recipes at the original HDF5 path, with a retained backup, failure-safe pre-replacement workflow and successful ToFScope reopening. Native commercial/third-party discovery is a separately reported Task 4 capability, never implied by a successful extension save.

## References

- [h5py maximum-shape limits](https://docs.h5py.org/en/stable/high/dataset.html#resizable-datasets).
- [h5py file handling](https://docs.h5py.org/en/stable/high/file.html).
- [filelock documentation](https://py-filelock.readthedocs.io/en/latest/).
