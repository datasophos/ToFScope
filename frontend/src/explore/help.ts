// Adapted from the frozen prototype's web/workspace.js, for the packaged pilot.
export const help = {
  workspace:
    "Open several acquisitions, or open the same file again for an independent analysis. Each tab keeps its own signal, ROI and depth selection. Closing a tab or workspace releases its analyses without modifying acquisition files. Workspaces are temporary and reset when the service restarts.",
  signal:
    "Search by mass or label, then choose a stored signal to update the images and depth profile. Stored signals use the acquisition's vendor-processed channels; a custom mass window reconstructs raw events instead.",
  comparisons:
    "Add stored signals as extra depth-profile curves without changing the active image signal. To compare a custom mass window, choose Add to comparisons before applying it. Each comparison keeps its own mass and integration-frame limits.",
  windows:
    "Drag horizontally on the mass spectrum or enter exact limits to edit the selected draft interval. Drag its gold edges to resize; Shift-drag the band to move it. Add intervals to combine separated peaks. Limits in Th and integration frames are inclusive. Editing does not read raw events: Apply custom window performs reconstruction, which can differ from vendor processing. Choose whether to replace the active signal or add a comparison.",
  roi: "Draw a rectangle on the ion map to select a spatial ROI, or enter exact zero-based, inclusive pixel limits and apply them. Drag the gold edges to resize; Shift-drag inside to move. Profiles use the original-resolution pixels. Reset to full field restores the complete image. SE images do not edit the SIMS ROI.",
  loaded:
    "Choose the inclusive first and last acquisition frames to load. This sets the available depth range for this analysis; the depth controls select a frame, a window or all depths within it. A custom integration retains the frame range used when it was applied.",
  display:
    "Log colors changes image contrast without changing measured values. Relative profiles scales each depth-profile curve to its own maximum. Neither changes scientific values in exports. Choose SIMS or the unregistered SE image; SE pixels are not aligned to the SIMS ROI. The spectrum has a separate Log y / Linear y control.",
  depth:
    "Frames are zero-based and limits are inclusive. Choose All depths to sum the loaded frame range, use arrows or the slider for one frame, or enter a window. Click a front projection or depth profile to select one frame; drag horizontally on the depth profile to select a window. Arrow keys navigate the focused analysis. The profile shows the full loaded range with the selected depth highlighted.",
  exports:
    "Profile CSV exports original-resolution depth-profile values. Settings JSON exports the current analysis settings. PNG exports a pane's current view. Display color scaling and relative profile scaling do not change exported scientific values. Exports create separate downloads; acquisition files remain read-only.",
  ion: "The ion map sums the active signal over the selected depth frames. Draw a rectangle to select a spatial ROI. Drag gold edges to resize; Shift-drag inside to move. The front projection sums the ROI's Y rows. Use Ctrl/Cmd-wheel to zoom horizontally; ordinary wheel movement scrolls the page. Reset zoom restores the view, PNG downloads it, and the arrow maximizes it; Escape restores the pane.",
  se: "SE images are paired by frame index and shown in native pixels. A depth window shows their unregistered mean, using actual pixel coverage. Registration and timing alignment are unverified, so this image does not define the SIMS ROI. Ctrl/Cmd-wheel zooms horizontally. Reset zoom, PNG and maximize affect this view only; Escape restores a maximized pane.",
  spectrum:
    "The mass spectrum is the acquisition's vendor-summed spectrum. Drag horizontally to edit a draft mass interval; drag gold edges to resize or Shift-drag to move. Apply custom window reconstructs raw events for images or a comparison profile. Log y / Linear y changes only the vertical display; zero samples are omitted in log mode. Ctrl/Cmd-wheel zooms horizontally. Zoom to draft focuses the selected interval; Reset zoom restores the full range. PNG and maximize act on this pane; Escape restores it.",
  front:
    "This projection sums the active signal along the spatial ROI's Y rows, showing X against acquisition frame. Click to select a depth frame. The values use original-resolution pixels. Ctrl/Cmd-wheel zooms horizontally; ordinary wheel movement scrolls. Reset zoom restores the view, PNG downloads it, and the arrow maximizes it; Escape restores the pane.",
  profile:
    "Each curve is the mean signal per original-resolution pixel within the spatial ROI. Click for one frame or drag horizontally to select a depth window. Drag gold edges to resize; Shift-drag to move. All depths clears the depth selection. Relative profiles scales each curve to its own maximum for display only. Ctrl/Cmd-wheel zooms horizontally; Reset zoom restores the range. PNG and maximize act on this pane; Escape restores it.",
};
