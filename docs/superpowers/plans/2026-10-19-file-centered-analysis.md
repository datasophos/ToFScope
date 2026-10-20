# File-centered Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace workspace management with independent file tabs and restore committed analyses from self-contained HDF5 copies.

**Architecture:** Keep original acquisitions immutable. Stream a byte-preserving acquisition copy, add versioned ToFScope analysis metadata and full-resolution custom results, verify the temporary file and publish without overwriting. Reuse owner/resource admission and the existing integration record format; restore saved results through the storage boundary without reintegration.

**Tech Stack:** Python, FastAPI, h5py/NumPy, React/TypeScript, ECharts, unittest and Playwright; bundled frontend assets.

**Spec:** `docs/superpowers/specs/2026-10-19-file-centered-analysis-design.md`, including the optional browser download amendment.

**Execution:** Inline execution, as already selected by the user. Status: approved in Plannotator with zero annotations; design approved by “continue” after incorporating the download feedback.

## Global constraints

- Original acquisitions remain immutable. Saving always creates a new file, including when the input is a previously saved copy.
- No legacy compatibility layers, database, runtime Node, CDN, external deployment or release publication.
- Preserve scientific numerical values, independent analyses of the same file, multiple open files and owner isolation.
- Saved files contain all committed signals, including hidden signals and full-resolution custom results. Opening does not depend on the original path, caches or reintegration.
- Saving defaults to a server-side file without starting a browser download. Download is explicit and warns that large files may take a long time.
- Pending drafts and calculations must finish or be discarded/cancelled before saving. An edited analysis invalidates a save before publication; saved state is tied to an explicit committed revision.
- Preserve the clean frozen prototype at `/private/tmp/tofscope-prototype-37ecacf`. Work only in the existing isolated implementation worktree.
- Commercial-native writes and modifications of original acquisitions remain unavailable. Saved-copy support does not enable the completion plan's native write feature.

## Review focus

1. Re-saving a saved file must restore the latest state without accumulating obsolete result volumes or dropping unrelated vendor content — Tasks 1–3.
2. Disk exhaustion, cancellation and name collisions must never leave a published partial file or replace another user's output — Tasks 2 and 4.
3. A saved file moved to a new server must use fresh owner/service identities and preserve shared signal relationships without trusting embedded paths — Tasks 1 and 3.
4. Closing or editing an analysis during a save must have an unambiguous outcome; an interrupted browser download must preserve the completed server file — Tasks 4–6.
5. Multiple browser tabs, partial coverage, hidden signals and evicted custom volumes must preserve exact values under memory/admission limits — Tasks 2–3 and 6–7.

## File map

- `storage/analysis_document.py`: versioned persisted state, strict validation, relationship remapping and HDF5 result references.
- `storage/saved_files.py`: output confinement, owner directories, temporary copies, verification and exclusive publication.
- `application/saves.py`: captured revision, save task execution, saved-file descriptors and cancellation.
- Existing `application/jobs.py`, `resources.py`: shared fair scheduling and resource admission for integration/save work.
- Existing `storage/integration_store.py`, `acquisitions.py` and `application/cache.py`: bounded persisted-result reads and cache identity.
- Existing `application/workspaces.py`: replace explicit grouping with owner-scoped analysis collection; rename to `application/analyses.py` and update imports directly.
- Existing API/config/CLI: typed analysis/save/download routes and persistent output root.
- Frontend `app/`, new `explore/SaveCopy.tsx` and `app/UnsavedChanges.tsx`: file shell, dirty tracking, save progress, explicit download and close decisions.
- Tests listed below cover storage, service, API, browser and independently installed packages.

Paths in the file map are relative to `src/tofscope/` unless stated otherwise.

## Task 1: Define the saved analysis document

**Files:** Create `src/tofscope/storage/analysis_document.py`, `tests/test_analysis_document.py`; modify `src/tofscope/application/models.py`, `src/tofscope/application/commands.py`, `src/tofscope/presentation/exports.py`.

**Interfaces:** `SavedAnalysisDocument` contains a version, document-local signal IDs and recipes, style indices, image/profile references, loaded frames, ROI, depth and display state. `encode_document(snapshot: AnalysisSnapshot) -> SavedAnalysisDocument`; `read_document(path: Path, limits: Settings) -> SavedAnalysisDocument | None`; `restore_snapshot(document, initial: AnalysisSnapshot) -> AnalysisSnapshot`. Add `SignalSnapshot.materialization_id: str | None = None` for immutable persisted custom data; keep the editable underlying recipe intact. Add `DisplaySettings.spectrum_log: bool = True` and the corresponding optional display command field, so spectrum Y scale is also restorable.

- [x] Write `test_document_round_trip`, `test_fresh_service_ids_preserve_relationships`, `test_invalid_metadata_fails_explicitly`, `test_plain_acquisition_has_no_document`, `test_spectrum_scale_round_trip`. Assert exact names, colors, hidden/visible sets, inclusive bounds and display values; exclude owner, job, lease, source path and cache identity. Validate schema, byte/count limits before allocation, distinct IDs, valid references, finite bounds and stored channel indices against acquisition metadata. Unknown/incomplete/corrupt documents raise a clear error.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_analysis_document.py`; confirm failures for the missing implementation.
- [x] Implement the interfaces. Store document JSON at `/ToFScope/Analysis/state_json`, schema version 1 and a completion marker. Reference existing `/ToFScope/Integrations/<uuid>` records for custom values; document schema is independent of settings JSON schema 4. Reuse strict recipe validation without importing old widget state or adding legacy document support.
- [x] Rerun the document tests and existing analysis/export tests to pass. Commit `Define versioned saved analysis documents.`

## Task 2: Write complete, verified, exclusive saved copies

**Files:** Create `src/tofscope/storage/saved_files.py`, `tests/test_saved_files.py`; modify `src/tofscope/storage/integration_store.py`, `src/tofscope/config.py`.

**Interfaces:** `SavedFile(id: str, name: str, size: int)` exposes no server path. `SavedFileStore(settings)` provides `owner_root(owner) -> Path`, `path(owner, file_id) -> Path`, and `publish_copy(owner, source: Path, document: SavedAnalysisDocument, frames: Callable[[str], Iterator[np.ndarray]], name: str, cancel: Event, progress: Callable, before_publish: Callable[[], None]) -> SavedFile`. Add `Settings.output_root: Path | None`; default to `Path.home() / '.local/share/tofscope/saved-acquisitions'`, never the temporary runtime directory. Use an owner hash subdirectory with private permissions. Require leaf `.h5` filenames, reject traversal, separators, aliases and collisions.

- [x] Write failing tests for exact vendor datasets/attributes and source hash preservation; disjoint intervals and partial custom coverage; cancellation; insufficient space/write errors; verification failure; existing destinations; hard-link/symlink aliases; two simultaneous saves to the same name; hostile owner/filename values; repeat save of a saved file. Include hidden custom signals and unrelated existing ToFScope content.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_saved_files.py`; establish failures.
- [x] Implement bounded byte copying with an 8-MiB buffer charged to the resource budget. Validate self-contained source layout before copying; do not use vendor-native PeakData reconstruction. Update only this document and its referenced integration records in the temporary copy; remove superseded records owned by the prior analysis document, preserve unrelated content. Reuse `IntegrationRecord` and `write_integration_group` for full-XY float32 frame streams and exact coverage.
- [x] Close/reopen the temporary copy and validate all document references, shapes, dtypes and numerical checksums. Flush/fsync before `before_publish`, then publish on the same filesystem using exclusive hard-link creation followed by temporary unlink; never use replacing rename. Refuse unsupported publication semantics clearly. All pre-publication errors remove the temporary file; crash leftovers are private and never listed as completed files. Reserve/release temporary disk capacity per output filesystem to prevent concurrent saves overcommitting available space.
- [x] Run storage tests to pass, including repeat-save size/result-record assertions and source hashes. Commit `Write self-contained HDF5 copies without overwriting sources.`

## Task 3: Restore saved results through the bounded reader

**Files:** Modify `src/tofscope/storage/acquisitions.py`, `src/tofscope/storage/integration_store.py`, `src/tofscope/application/cache.py`, `src/tofscope/application/workspaces.py`, `src/tofscope/application/signals.py`, `src/tofscope/presentation/explore.py`, `src/tofscope/application/explore.py`, `src/tofscope/application/jobs.py`; create `tests/test_saved_analysis_restore.py`.

**Interfaces:** Add optional `materialization_id` to `AcquisitionRepository.read(...)` and `ArrayCache.load(...)`; include it in cache computation identity. Add `iter_saved_frames(path, saved_id, frames) -> Iterator[np.ndarray]` and `saved_result_info(path, saved_id)` with shape/dtype/coverage validation. Open and replace construct a fresh initial analysis then apply `restore_snapshot` if a document exists. Metadata references point to local integration IDs, never external paths.

- [x] Write failing tests saving multiple stored/custom signals, overlapping unions and unequal frame coverage, restarting services, deleting the original input, and opening as another authorized owner. Patch raw integration to raise during restored reads: images/profiles/CSV must still match exactly. Test evicted and hidden results, malformed arrays, cache accounting/handle release, concurrent reads and fresh identity remapping.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_saved_analysis_restore.py`; establish failures.
- [x] Restore custom signal recipes with their materialization IDs and read persisted values under existing allocation admission. Never call the existing unbounded `read_saved_integration` before reserving memory. Stream validation separately from admitted full-array cache reads. Persisted values preserve recipe provenance and remain editable; successful recalculation clears the materialization ID, while rename/display changes retain it. Duplication carries the correct derivation and does not silently substitute a vendor channel.
- [x] Thread the new data reference through every presenter/cache caller, including hidden-signal saves and exports. Fail restoration before publishing an analysis into the owner collection; quotas and missing coverage remain enforced.
- [x] Run restore, repository, cache, signal-job and numerical profile tests to pass. Commit `Restore saved signals without raw reintegration.`

## Task 4: Schedule saves and expose secure file APIs

**Files:** Create `src/tofscope/application/saves.py`, `tests/test_save_jobs.py`, `tests/test_save_api.py`; modify `src/tofscope/application/jobs.py`, `src/tofscope/api/{app,schemas}.py`, `src/tofscope/config.py`, `src/tofscope/cli.py`, `src/tofscope/storage/file_browser.py`, `src/tofscope/storage/acquisitions.py`.

**Interfaces:** `SaveService.submit(owner, analysis_id, revision_envelope, filename) -> JobSnapshot`; shared job records gain `kind: Literal['integration','save']` and `saved_file: SavedFile | None`. Extend the existing JobService fair queue with typed save work and a registered execution handler; use the same owner/global/per-analysis quotas, deduplication, cancellation and shutdown rules. `SaveService.run(task, cancel, progress)` captures immutable document state and iterates one admitted signal volume at a time. New routes: `POST /analyses/{id}/saves`, `GET /saved-files`, `GET /saved-files/{id}/download`; save status/cancel use existing `/jobs/{id}` routes.

- [ ] Write failing tests for busy integration rejection, stale source/revision rejection, idempotent request retry, cancellation/close before commit, concurrent analyses, fair integration/save scheduling, reservations released on all failures, fresh-owner file isolation and unauthorized status/download access. Race publication against analysis edit/close; after publication, later UI failures must not undo a valid file.
- [ ] Run the save service/API tests to establish failures.
- [ ] Implement save scheduling without reserving every result simultaneously or monopolizing API threads. Capture snapshot under the analysis lock, do copy/verification outside it, then hold the lock across final revision/source checks and exclusive publication. Saving itself does not advance scientific state. Return the committed source revision in the completed save result for UI dirty tracking.
- [ ] Add output-root CLI/env/TOML support with existing precedence; separate `original_writes: false` from `save_copies: true` in health/capabilities and remove the blanket CLI claim that no output can be written. Leave native-write opt-ins ineffective for original acquisitions in this feature.
- [ ] Add explicit acquisition/saved location selection to file browsing/open requests and `DatasetRef`; default location is acquisition. Resolve saved IDs only inside the current owner's output directory and require authorization for every read, replacement and download. Keep repository identities based on the resolved local file; never trust embedded file paths. Do not expose output-root absolute paths.
- [ ] Stream optional downloads in bounded chunks using owner-authenticated requests; release buffers/handles on disconnect. Reject files replaced after validation; preserve outputs on disconnect. Send an attachment filename without constructing a complete response in RAM.
- [ ] Regenerate OpenAPI/types after tests pass. Commit `Schedule owner-scoped saves and stream optional downloads.`

## Task 5: Replace public workspaces with a file collection

**Files:** Rename `src/tofscope/application/workspaces.py` to `analyses.py`; modify application imports/models/lifecycle, `api/app.py`, `frontend/src/app/App.tsx`, `frontend/src/api/client.ts`, `frontend/src/explore/help.ts`; adapt existing API/service/browser tests and scripts directly.

**Interfaces:** `AnalysisService.list(owner) -> list[AnalysisSnapshot]`, `create_analysis(owner, dataset)`, existing `entry/get/replace/close` behavior remains owner-scoped. Use `GET /analyses` and `POST /analyses` for the live owner collection; remove WorkspaceSnapshot, WorkspaceStore and `/workspaces` routes. Existing lease recovery remains automatic and internal. Persist active tab choice in browser session storage, not an exposed workspace ID.

- [ ] Write failing API/browser checks proving an empty screen contains Open acquisition but no workspace selector, Close workspace, analysis-ID field or reconnect form. Verify two users, A/B/A independent tabs, same-file analyses, reload, expired leases, failed open, service restart and initial-file launch. Closing one analysis must never close another.
- [ ] Run the relevant tests and confirm failures from the old interface.
- [ ] Replace grouping wholesale with the owner collection, retaining quotas, cancellation callbacks and source-generation checks. Remove manual recovery UI and temporary-workspace copy. Keep open tabs automatically recoverable while their service entries live; a restart gives an empty file collection and saved files remain reopenable.
- [ ] Update all first-party tests/scripts to the new routes rather than adding compatibility endpoints. Regenerate API types; run lifecycle, owner/concurrency and browser checks to pass. Commit `Replace workspace management with independent file tabs.`

## Task 6: Add Save as, dirty tracking and explicit downloads

**Files:** Create `frontend/src/explore/SaveCopy.tsx`, `frontend/src/app/UnsavedChanges.tsx`, `frontend/e2e/saved-files.spec.ts`; modify `ExploreScreen.tsx`, `app/App.tsx`, `app/FilePicker.tsx`, `app/useAnalysis.ts`, `api/client.ts`, plot display ownership, styles and help.

**Interfaces:** SaveCopy receives current Analysis, whether a draft/integration is pending, and an `onSaved({file, revision})` callback. Track saved revision per live analysis; ordinary acquisitions start unsaved, restored documents start clean. UnsavedChanges returns Save as / Discard / Cancel decisions. Save dialog supplies filename, progress, cancellation, clear failure state and an optional Download action after success. File picker has Acquisitions and Saved files locations.

- [ ] Write failing Playwright tests for complete save/restart/reopen restoration, dirty/clean indicators, failed/cancelled save preserving dirty state, uncommitted draft/busy explanations, edited-during-save conflict, per-tab close decisions and tab independence. Save must not trigger a download event; clicking Download must, with the large-transfer notice visible first. Test interrupted download leaves Saved files entry available.
- [ ] Test pending draft on an otherwise clean document still prompts on close; changing spectrum Log y / Linear y must persist and dirty the analysis. Cover close/replace of both ordinary and restored files. Browser/window close can warn through beforeunload; do not promise an asynchronous save during browser teardown.
- [ ] Run the tests to establish failures. Implement Save as with explicit name entry and no server path field, async status polling and cancel, errors retaining entered name, and Download off by default. Preserve spectrum toggle immediacy through optimistic/local display feedback while committing the shared display setting.
- [ ] Integrate saved-revision notifications from useAnalysis into the shell instead of reading stale initial props. After close → Save as, close only on successful publication of the still-current revision; failed saves keep the tab/draft. Keep Save as disabled during uncommitted work and guide the user to finish/discard first.
- [ ] Remove Settings JSON from the primary actions in favor of Save as; keep Profile CSV and PNG for numerical/visual export. The existing JSON export may remain an explicit diagnostic endpoint, not the restoration workflow. Update brand/help copy to “Original acquisitions are read only” rather than suggesting saved copies cannot be created.
- [ ] Run typecheck, unit/browser checks, narrow layouts and existing plot-performance checks to pass. Commit `Save and reopen file-based analyses from the Explore interface.`

## Task 7: Qualify packaged saves and update future-feature context

**Files:** Modify `scripts/check_distribution.py`, `scripts/check_real_browser.py`, `README.md`, `docs/deployment.md`, `docs/hdf5-compatibility.md`, `docs/react-fastapi-migration.md`, `docs/superpowers/plans/2026-10-18-react-fastapi-completion.md`; create `scripts/check_saved_copy.py`, `docs/validation/file-centered-analysis.md`.

- [ ] Extend the installed wheel/sdist smoke to save stored/custom/hidden signals, restart the installed service, remove its original disposable fixture, reopen the saved file, assert exact profile/settings state and exercise optional download. Block external browser requests and run with no Node in runtime PATH. Verify no automatic download on save.
- [ ] Add read-only real-source qualification: write output only to a task-specific temporary directory; compare original file identity/hash, vendor metadata/data, full-resolution custom arrays and selected ROI profiles after restart/source-independent reopen. Include two owners/independent analyses, cancellation and resource high-water evidence. Do not move/delete/edit the real source; use a copied fixture when proving source removal.
- [ ] Run `.venv/bin/python -m unittest discover -s tests`, `npm --prefix frontend run typecheck`, `npm --prefix frontend test`, `npm --prefix frontend run test:e2e`, `python3 scripts/build_frontend.py`, then build fresh wheel/sdist and execute the updated distribution smoke. Report original-write denial separately from successful new-file saves. Run real-data qualification only if readable; leave NFS/commercial-tool/hardware results explicitly unverified unless actually observed.
- [ ] Update launch instructions with persistent output-root behavior and disk requirements; state that browser download is optional and may take a long time. Mark the completion plan's separate native-save feature still deferred; record the new embedded state as context for calibration/identification/3D without claiming their state is already implemented.
- [ ] Review storage/publication and owner boundaries, run `git diff --check`, confirm frozen prototype remains clean, and commit `Qualify packaged file-centered analysis persistence.` Do not publish or deploy. Summarize launch instructions, passed/blocked checks and remaining limitations.

## Plan self-review

The seven tasks cover the approved spec and download amendment. Document validation precedes publication; persisted materializations remain separate from editable derivations. Owner-scoped output browsing and paths are covered, including restart and relocation. Original-write controls remain distinct. Close/draft and saved-revision races are explicit. The old workspace interface is removed directly. Each task ends with focused verification and a coherent commit; package qualification happens after the final frontend build.
