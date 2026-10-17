# Server File Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Implementation requires a separate user instruction; this plan is a proposed design.

**Goal:** Browse and open acquisitions within a configurable server data directory.

**Architecture:** Add a server-owned root policy and a directory listing service, then replace free-form server paths with a scoped file picker. All open/write entry points use the same policy; listing does not open every HDF5 file.

**Tech Stack:** Python pathlib, h5py, environment configuration, AnyWidget, unittest, Playwright

**Spec:** [Roadmap design brief, section 2](../specs/2026-10-16-roadmap-design.md).

## Global Constraints

- Keep Marimo + AnyWidget + Plotly; do not introduce Panel.
- Treat frame limits as zero-based and inclusive.
- Do not change source HDF5 files except through explicit write-back.
- Preserve existing shared ROI, All depths, maximize/restore, and offline operation.
- Scientific transforms must not silently change analysis intensities.

## Dependencies and file boundaries

Independent of other roadmap plans. Create `server_config.py` for settings and root policy, `file_browser.py` for shallow directory pages, and `web/file_browser.js` for the dialog. The controller remains responsible for loading selected datasets, not traversing the filesystem itself.

## Review Focus

- `..`, absolute paths and symlinks outside the configured root must be rejected for listing and opening (Task 1).
- Empty, missing and unreadable directories must leave a usable browser (Tasks 1, 3).
- A directory containing thousands of files must not trigger eager HDF5 reads (Task 2).
- Files deleted or permissions changed between listing and opening must leave the current dataset intact (Task 3).
- Root restrictions must apply to legacy/custom messages and future write targets, not only picker clicks (Tasks 1, 3).

### Task 1: Define configuration and enforce one path policy

**Files:** Create `server_config.py`, `tests/test_server_config.py`; modify `app.py`, `workspace.py`.

**Interfaces:** Frozen `ServerSettings(data_root: Path, allow_writes: bool=False, initial_file: Path|None=None)`; `load_server_settings(env: Mapping[str,str]) -> ServerSettings`; `resolve_data_path(settings, relative_path: str, *, require_file: bool=False) -> Path`. The last function returns the canonical contained path, not the user's unvalidated string.

- [x] Write tests for configured/default demo roots, `TOF_FILE` validation, missing roots, rejected invalid booleans, and `TOFSCOPE_ALLOW_WRITES=false` by default. An initial file outside the root is an actionable configuration error.
- [x] Test `../outside.h5`, absolute paths, sibling-prefix confusion (`data-other`), escaping directory/file symlinks, and allowed in-root symlinks. Use temporary directories, not client files.
- [x] Run `uv run python -m unittest discover -s tests -p 'test_server_config.py' -v`; verify failure, then implement environment parsing and canonical `Path.relative_to` containment after resolution. Document the trusted-root ownership assumption.
- [x] Pass settings into `ExplorerWorkspace`; make every `open` path resolve through this helper, even messages from the old path-input UI. Keep internal absolute paths private; publish root-relative dataset paths to browser state/recipes when scoped browsing is enabled.
- [x] Run config tests and existing dataset-opening tests. Commit: `Configure and enforce the server data root.`

### Task 2: Provide bounded directory listings

**Files:** Create `file_browser.py`, `tests/test_file_browser.py`; modify `workspace.py`.

**Interfaces:** `list_data_files(settings, relative_dir: str='', *, query: str='', offset: int=0, limit: int=100) -> DirectoryPage`; entries contain root-relative path, name, kind, file size and modification time. `DirectoryPage` contains entries, total matches and next offset; enforce `1 <= limit <= 200`. Event `files_list` returns a separate `files` response without replacing acquisition state.

- [x] Write tests for directories-first/name sorting, `.h5`/`.hdf5` case-insensitive filtering, query filtering, pagination, and suppression of dot-prefixed backup/temp/lock entries. Directory pages never include an outside-root target.
- [x] Add a 5,000-entry fixture and patch `h5py.File` to raise if called during listing; listing must still succeed. Test unreadable directories and a disappearing file using controlled mocks where platform permissions make chmod unreliable.
- [x] Run `uv run python -m unittest discover -s tests -p 'test_file_browser.py' -v`; verify failure, then implement shallow `os.scandir` enumeration, filtering and page metadata. Do not recurse or inspect peak arrays while listing.
- [x] Add `files_list` validation and structured errors to the widget message handler. Resolve paths again when opening; do not trust a previously displayed listing entry or offset as authorization.
- [x] Run both new test modules. Commit: `List server acquisitions with scoped pagination.`

### Task 3: Ship the file picker and empty startup state

**Files:** Create `web/file_browser.js`, `scripts/check_file_browser.py`; modify `web/workspace.js`, `web/workspace.css`, `workspace.py`, `app.py`, `README.md`.

**Interfaces:** Browser component `mountFileBrowser(root, {requestPage, openFile}) -> {update, dispose}`; opens use root-relative paths. `ExplorerWorkspace(path=None, settings=...)` must represent an unloaded dataset without attempting plots/ROI calculations; opening a valid file transitions to the existing loaded state.

- [x] Write a failing browser scenario with a temporary configured root: open subdirectory via breadcrumbs, filter, page, choose a file, and return to the parent. Assert successful dataset switch and no path outside the root in the picker.
- [x] Test an empty root/no initial file, unsupported HDF5, missing file after listing, and direct forged `open`/`files_list` messages. A failed load preserves the prior dataset and closes no usable view. When unloaded, analysis/export controls stay disabled while Open file remains usable.
- [x] Implement a keyboard-accessible dialog with breadcrumbs, search, list, loading/error/empty states and explicit Open. Remove the free-form absolute server path input. Reset selection when changing directories and ignore stale listing responses using a request ID.
- [x] Run `uv run python scripts/check_file_browser.py` against its fixture-configured server plus all config/list tests and `uv run marimo check app.py`. Document `TOFSCOPE_DATA_ROOT=/path/to/acquisitions`, `TOF_FILE` and read-only defaults without adding remote hosting/authentication scope.
- [x] Commit: `Browse server files from the acquisition picker.`

## Acceptance

Users can browse a configured data tree without knowing server absolute paths. Empty roots are usable, opening invalid files does not lose analysis state, and crafted messages cannot bypass the root policy.
