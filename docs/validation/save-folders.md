# Save folders

Save as reuses the file explorer in folder-selection mode. Choose folder opens
at the current destination, supports breadcrumbs, parent navigation, search,
pagination and folder creation. Cancel preserves the destination. The save form
keeps the filename separate and shows the full resulting server path. Saved files
in the open picker now includes directories so nested copies can be reopened.

Local authenticated users can choose within configured data_root and output_root.
Hosted users remain in their private owner output directory. Absolute supplied
folder paths, parent traversal, symlink folders and cross-owner access are
rejected. Encoded IDs preserve legacy root-file IDs, support owner-relative
nested files, and restrict local acquisition-location IDs to the configured data
root. Folder choice is captured in the save job and idempotency envelope. Exclusive
publication continues to reject filename collisions; originals stay unchanged.

Folder creation reports duplicate names as actionable validation errors. Missing
folders return an expected error. A failed creation leaves the current folder
selectable. Selection controls are disabled during saves. The picker and full
path preview were checked on desktop and at 560px viewport width.

Validation:

- 196 Python tests passed, including nested save/download/reopen, owner isolation,
  configured local data-folder selection, traversal/absolute-path/symlink rejection
  and duplicate-folder errors. The 25 save-focused tests passed again after the
  final idempotency/preflight adjustment.
- 12 browser workflows passed for shared open/save behavior, folder creation,
  cancelled folder selection, exact destination preview, nested download/reopen
  and the narrow folder-picker layout.
- 30 frontend tests, TypeScript and the packaged asset build passed.
- Independent review found one duplicate-folder error issue, fixed and verified;
  the follow-up review found no remaining actionable issues.

[Choose folder](save-folders/save-folder-picker.png) ·
[Destination preview](save-folders/save-destination.png)

Activating these backend changes in an existing local service requires a restart.
Open analyses reside in memory and should be saved before restarting.


The sidebar location buttons explicitly size themselves for both label lines,
preventing inherited page-header button heights from clipping the folder names.
A browser geometry assertion reproduces the clipping and verifies both location
subtitles fit inside their buttons when launched from Save as. All 11 open/save
browser workflows and the packaged build passed after the style correction.


The filename input and Save copy button share a 36px height and matching font,
with their top and bottom edges aligned. A geometry assertion catches inherited
compact header-button styles overriding the save form. All seven save/reopen
browser workflows and the packaged build passed after this correction.
