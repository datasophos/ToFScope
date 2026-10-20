# File-centered analysis and saved HDF5 copies

Status: proposed for user review. This supersedes user-facing workspace grouping
and manual analysis-ID reattachment. It expands the Explore pilot to writing new
output files; original acquisitions remain immutable.

## Intended experience

Users open HDF5 files, analyze them in independent tabs, and save a new HDF5 copy
when they want to retain their work. They should not manage workspace containers
or reconnect using internal analysis IDs. Opening a saved copy restores its
committed scientific results and analysis settings, including after a service
restart or moving the file to another computer.

Remove the workspace selector, Close workspace, manual reattachment form and
workspace lifecycle copy from the interface. Keep Open acquisition, independent
file tabs, and per-tab close. Internal ownership, admission limits, leases and
recovery of live tabs remain service concerns. No workspace IDs become file
metadata or user-facing recovery requirements.

## Save a copy

Add Save as… to an analysis. The result is a full, self-contained HDF5 copy with
original acquisition content preserved and ToFScope state in a versioned
`/ToFScope` group. Do not rebuild vendor PeakData or turn custom unions into
vendor-native channels. This is distinct from the completion plan's experimental
native writes and makes no commercial-software compatibility claim.

Store committed signal names, identities within the document, stable colors,
recipes, coverage and custom numerical results; image/profile selections; ROI;
analysis frame range; viewing depths; image choice; and display settings. Store
custom results at original spatial resolution and numerical precision, including
hidden signals. Reading the saved file must not require the original path,
external caches, or reintegration. Exclude pending drafts, job IDs, leases,
credentials and server ownership. Service instances assign fresh internal analysis
and signal IDs on open while preserving saved document relationships.

Saving uses an explicit committed revision. Disable saving during calculations or
an uncommitted signal draft, with a concise explanation and access to finish or
discard the draft. Track whether the current revision has been saved; closing an
unsaved tab offers Save as…, Discard, or Cancel. Original source files remain
unchanged even when the current input is itself a previously saved copy.

The initial copy duplicates the acquisition bytes, so a 2.2-GB acquisition needs
at least that much output space, plus custom results and metadata. Use background
work with progress/cancellation and existing owner/resource admission. Avoid
loading the complete acquisition into RAM. Saved custom volumes use bounded
chunks; evicted volumes can be reconstructed during saving under the same limits.

## Storage and publication

Use a configured server output directory and confined filenames, never arbitrary
client filesystem paths. Include saved files in the file picker. Saving defaults
to a server-side file without starting a browser download. Offer an explicit, non-default Download
action for the completed HDF5 copy, with a notice that large files may take a
long time to transfer. Stream downloads with bounded memory and owner-scoped
authorization; a failed or cancelled download does not remove the saved copy.
Never overwrite an existing file, the input, or a hard-link alias of it.

Create a private temporary sibling, stream-copy the source, add ToFScope content,
close every handle, reopen and validate, then publish atomically without replacing
an existing destination. Recheck source generation and the captured revision;
changes invalidate the save before publication. Cancellation/failure removes
partial output and leaves originals and existing outputs intact. Report disk
space, invalid schema and unsupported external-link layouts clearly. Do not claim
self-contained output for files depending on external storage.

## Restore and validation

Treat embedded metadata as untrusted input: validate schema version, shapes,
coverage, finite bounds, signal counts and resource limits. Unsupported/corrupt
ToFScope state must produce a clear error rather than silently opening a default
analysis and suggesting restoration succeeded. Unannotated acquisitions open with
normal defaults. Keep API contracts independent of reader and plot backends.

Verify an exact round trip of multiple stored/custom/hidden signals, disjoint mass
intervals, partial coverage, ROI, selections and display state after restart and
source removal. Compare custom arrays and original-resolution profiles exactly.
Test fresh-owner isolation, concurrent independent saves, cancellation, stale
revisions, disk failures, filename collisions, aliases and malformed metadata.
Verify that saving starts no browser download by default, the optional download
streams the complete saved file, and interrupting a transfer preserves the saved
copy. Check original hashes and vendor datasets/attributes before and after saving.
Verify packaged wheel/sdist workflows offline without Node/CDNs. Real-data and
filesystem-specific checks must retain explicit passed/unverified distinctions.
