# Explore signal workspace redesign

Date: 2026-10-19
Status: Written spec approved by Josh on 2026-10-19; implementation plan approved; inline execution underway.

## Purpose and approved direction

Replace the Explore sidebar with a signal tray above the plots, controls near
those plots, and a temporary editor beside the mass spectrum. Users should be
able to identify what exists, what each plot shows, what is being edited, and
what actions are available without reading contextual help.

Josh approved this combination after considering a signal tray, plot-local
controls, and a bottom signal workbench. This document makes the combined
approach concrete. It supersedes the pilot's active/comparison UI and state
model; the migration design and completion plan remain context for other features.

The application remains one installable Python service with bundled offline
frontend assets. Retain the scientific reader and renderer independence,
read-only acquisitions, bounded resource use, owner isolation, multiple files,
and independent analyses of the same acquisition. Keep the frozen prototype
checkout intact. Do not publish or deploy externally.

## Problems being addressed

- Active and comparison are currently distinct backend destinations as well as
  UI choices. Users must choose a destination before computing a signal.
- The selected draft mass interval, committed image signal, and integration
  frame limits can describe different states without clearly identifying them.
- Loaded frames, integration frames, and displayed depths appear as similarly
  named controls despite affecting different things.
- A permanent scrolling sidebar places actions far from the affected plots and
  hides much of the current state.

## Signal model

An analysis owns an ordered collection of signals. Each signal has a stable ID,
user-visible name, creation ordinal for a stable line style, committed scientific
recipe when available, and recipe version. Scientific provenance remains explicit:
stored channel or raw integration; exact mass intervals and inclusive frame
coverage are always available in details. User naming does not change provenance
or computation identity. Scientific recipes remain library-independent.

Display state references signal IDs:

- Exactly one ready signal supplies the SIMS ion map and front projection.
- That signal always appears in the depth profile.
- Other ready signals may be shown or hidden in the profile independently.
- Hiding or switching a signal does not delete its recipe or change its name,
  color, calculation frame coverage, or computed values.
- Display choices belong to the analysis and survive browser refresh/reattach
  within the current service lifetime. Service restart still resets workspaces.

Opening an acquisition registers the existing default stored channel and selects
it for images and profiles. Other stored channels remain searchable candidates;
opening a file does not load every channel. New custom signals join the tray and
profile after successful calculation, without replacing the image signal.

IDs and style ordinals remain stable when a signal is renamed, edited, removed
from a profile, or chosen for images. Removing a signal does not recolor survivors.
Name collisions are allowed but the tray and legend include enough provenance
and frame coverage to distinguish them. Empty names are rejected.

## Main layout

Keep acquisition tabs, file actions, branding, and help. Replace the sidebar with:

1. A signal tray spanning the workspace width.
2. A shared Viewing depths strip above the plots.
3. The existing square ion-map/front-projection column and wider mass-spectrum/
   depth-profile column, preserving the corrected order and responsive sizing.
4. A compact analysis-scope note below the plots.

The tray has Add stored signal and Create from spectrum actions, plus rows with:
color marker, name and source, Images radio button, Profile checkbox, and actions.
A compact coverage summary appears when coverage differs from the analysis range.
Details exposes exact provenance without an oversized always-visible form.
The tray shows up to four rows before scrolling; its header and column labels
remain visible. It is not automatically collapsed when state changes.

The Images radio button is labeled by signal name. The image signal's Profile
checkbox is checked and disabled with an explanation: included with image signal.
Other checkboxes simply show/hide profile curves. Previously selected image
signals remain profile-visible until explicitly hidden.

Selecting a row opens its details; it does not change image or profile choices.
A successful custom calculation exposes Show in images as a direct follow-up.
Pending signals have no enabled display controls until they have a ready result.

On narrow screens rows become compact cards retaining the same explicit labels.
The plots stack in the current reading order. There is no horizontal page overflow.
The editor appears directly above the spectrum rather than squeezing the plot.

## Adding, inspecting, editing, and removing signals

Add stored signal opens the existing searchable bounded picker in an accessible
popover. Choosing a channel adds a ready signal to the profile. If that same
stored channel and frame coverage already exists, focus its row and show its
profile rather than adding an accidental duplicate. An intentional duplicate is
available through the signal's Duplicate action.

Stored signal details show its channel, bounds, and coverage; they do not imply
that vendor-processed values can be edited. Create custom copy opens a raw
integration draft seeded with those bounds and clearly labels the source change.

Custom signal actions are Edit, Duplicate, Rename, and Remove. Duplicate opens
a new draft seeded from the committed recipe with a distinct proposed name.
It does not mutate or automatically recalculate the original signal.

Remove cancels that signal's pending work and releases its held resources.
Removing the image signal selects the first remaining ready signal in tray order
whose coverage intersects the analysis range, and keeps it visible in the profile.
If no other ready signal has usable coverage, Remove is
disabled with an explanation; users can add another signal first. A new pending
signal can be removed without affecting ready signals.

## Spectrum editor

Create from spectrum opens one editor per analysis with a suggested name,
editable exact mass bounds, Add interval, Calculate over frame coverage, and
Calculate signal / Discard actions. No spectrum draft exists until this action
or Edit / Create custom copy opens the editor. The spectrum displays a concise
mode indicator: Viewing spectrum, Creating <name>, or Editing <name>.

In editor mode, drawing on the spectrum edits the selected draft interval.
Selecting another interval explicitly chooses the one subsequent gestures edit.
Intervals have thin outlines, faint fill, and the existing generous invisible
resize targets. Bounds retain full numeric precision; formatting in summaries
must not round-trip back into the scientific recipe. Multiple intervals form
one union signal; overlapping events are counted once.

In viewing mode spectrum drag zooms horizontally; it does not create a draft.
Ctrl/Cmd-wheel and Reset zoom remain available in either mode. Ordinary wheel
continues to scroll the page. Creating/editing a signal never changes the current
image, profile values, or committed names before calculation succeeds.

For edits, show Changes not calculated and Update signal. For creation, show
New signal and Calculate signal. Discard closes the draft without changing
committed data. Opening another draft while a dirty draft exists presents explicit
Keep editing / Discard and continue actions within the editor. One analysis's
draft never changes another analysis or file tab.

On a wide screen the editor is a temporary panel beside the spectrum within its
column, not a viewport-wide modal or a permanent left sidebar. Maximize spectrum
retains access to the editor and full-precision fields.

## Calculation lifecycle and concurrency

Submitting an editor freezes its submitted recipe and starts bounded background
work for that signal ID. Show Queued or Calculating, completed/total frames, and
Cancel on the corresponding row and editor. Other signals and display controls
remain usable. Keep the editor read-only during its submitted job; successful
completion closes it. A draft can be reopened afterward for another edit.

A new signal has a pending row until successful publication. Updating an existing
signal retains its old committed recipe, name, and values with an Updating badge.
Publish the submitted name, recipe, coverage, and new values atomically only on
success. If it supplies images, keep its identity and update affected plots with
an explicit loading indicator. Never label old data as the new result while
waiting for panel data; publish matching panel versions or mark the old panel
as updating until replacement arrives.

Cancellation, failure, and obsolete source/recipe versions preserve the old
committed signal. Keep the submitted draft available for correction/retry and
show a specific error near it. Removing a new failed/pending row removes its draft.

Job targets are signal IDs and recipe-version tokens, not active/comparison slots.
Unrelated display changes, ROI changes, and renames do not invalidate a scientific
calculation. A rename made after job submission takes precedence over the submitted
name when results are published; completion cannot revert a newer explicit rename. Deleting a signal, replacing its acquisition, closing the analysis,
or submitting a superseding recipe prevents late publication. Retries with the
same request ID are idempotent. Retain owner checks, revision conflicts, fair
per-user scheduling, source validation, cancellation and memory admission.

Promoting a resident signal to images does not reintegrate raw data or fetch an
unrelated spectrum. Resource eviction may require bounded rereading/recalculation;
show that preparation explicitly rather than promising permanent residency.
Hidden signals retain recipes without pinning every full volume in memory.
Global/per-owner/per-analysis quotas cover the whole signal collection, including
hidden and pending rows; hiding signals cannot bypass resource limits.

## Frame coverage and view selection

Use distinct vocabulary and behavior:

- Calculate over frames: immutable coverage of a submitted signal recipe.
  Default to the current analysis range. Editing this field does not run a job.
- Viewing depths: current single frame, depth window, or all available depths.
  This changes the image sum and selected-depth marker, not a signal recipe.
- Analysis frame range: the profile domain and navigation limits. Expose this
  less frequent control in Analysis settings rather than in the signal editor.

Changing the analysis range does not silently rewrite existing signal recipes.
Newly added stored signals use that range; an existing stored signal's coverage
can be changed explicitly through its details without pretending it is a raw
integration. Custom coverage changes require Update signal.

Selecting a signal for images intersects the current viewing selection with its
coverage and the analysis range. If the intersection is empty, choose its first
available frame and announce the change. Disable image selection when no coverage
intersects the analysis range, with a clear explanation. All depths means all
available depths for the image signal within the analysis range; display the
resolved frame bounds. Profile curves retain the analysis domain and use nulls
outside their coverage. Missing coverage is never represented as zero.

## Controls and visible state near plots

- Ion map: title identifies the signal, Showing frames summary, clickable ROI
  summary, Log colors, and SIMS/SE choice when SE data exists.
- ROI summary opens exact zero-based inclusive fields plus Full field. Drawing
  on the SIMS image still edits the ROI. SE remains unregistered and cannot edit
  the SIMS ROI; a clear state label accompanies its native pixel axes.
- Front projection: identifies the same SIMS signal even while SE is displayed,
  retains click-to-select-depth and the exact ROI-Y projection semantics.
- Depth profile: interactive legend, Relative / Absolute control, clickable depth
  selection summary, All depths, zoom, PNG and maximize. Legend details/actions
  refer to the same signal IDs as the tray. Hiding an extra curve updates its tray
  checkbox; the image curve remains included.
- Mass spectrum: vendor-summed provenance in help/details, Log y / Linear y,
  Create signal, contextual draft zoom, reset, PNG and maximize.

Log colors, relative profiles, and spectrum log Y remain defaults. Keep loading
indicators, contextual help, Escape behavior, keyboard navigation, PNG exports
with legends, and the fast raster resize/maximize path. Plot-only state changes
must not launch scientific jobs or trigger unrelated data fetches.

## Application/API changes and implementation boundaries

Replace the old active_recipe/comparisons snapshot and destination commands
wholesale. Use a signal collection, image signal ID, profile visibility, recipe
versions, and explicit create/edit/remove/display operations. Replace job target
slots with signal targets. Replace the old interface in generated TypeScript,
exports and tests together; do not build legacy adapters for this unreleased app.

Keep acquisition access, numerical integration, and the renderer adapter behind
their existing boundaries. The API expresses arrays, axes, coverage, signals,
jobs and view state; it contains no ECharts options or reader-library objects.

Extract focused frontend components: SignalTray, SignalDetails, SignalEditor,
ViewingDepths, ROI controls, and plot-local display controls. Keep asynchronous
signal/editor state and version-aware panel acceptance out of a giant screen
component. Authoritative signals, names, visibility and jobs live on the server;
unsaved input strings and editor interaction state remain local to each analysis.

Settings JSON exports all committed signals, provenance, frame coverage, image
selection, profile visibility, ROI and display settings in a new explicit schema.
It does not claim pending drafts are committed results. CSV exports currently
visible profile curves with stable identifying headers and original numerical
values, preserving existing selected-window scope and null coverage. Hidden
signals remain in settings but not in the visible-profile CSV. Recipe import and
acquisition save remain unavailable.

## Verification and acceptance

1. Service tests cover creation, deduplication, explicit duplicate, rename, edit,
   display choice, hide/show and removal with stable identities and style ordinals.
2. Numerical tests compare stored channels, exact raw interval unions, ROI means,
   projections, inclusive endpoints, null coverage and CSV against existing
   references. Presentation changes cannot alter the frozen scientific results.
3. Job tests cover success, failure, cancellation, request retry, source change,
   close/remove, same-signal supersession, and display/ROI changes during a job.
4. Isolation tests cover two users, two files and two analyses of the same file,
   including separate drafts, independent signal choices and denied foreign IDs.
5. Browser checks demonstrate the complete creation/edit flow, explicit spectrum
   modes, pending-versus-committed labels, switching an existing signal to images,
   hiding/restoring a curve, legend consistency, full-precision input, and exports.
6. Browser checks cover responsive layout, scroll access, accessible radio/checkbox
   names, focus return, contextual help and dirty-draft handling.
7. Retain the full-size image resize/maximize regression. Use request/job assertions
   to prove resident signal display changes do not start reintegration. Record real
   acquisition timings where available without conflating local checks with NFS,
   hardware or external-service qualification.
8. Run the Python and frontend suites, regenerate API types, build bundled assets,
   and perform installed-package offline launch/plot/integration/export checks.
   Continue to require one service/port, no runtime Node/CDN and read-only sources.

Implement in the existing isolated workspace with coherent commits. Record
passed and unavailable checks separately. Do not restart the user's live service
as part of design work; deployment of the new backend requires a restart and
resets temporary workspaces, which must be communicated explicitly.
