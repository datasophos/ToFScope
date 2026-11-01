export const help = {
  signal:
    "Choose a signal under Images to change the ion map and front projection. Profiles lists the curves shown in the depth profile; select a name for details or × to hide a curve. Add signal offers stored signals and an option to create one from the spectrum. Use Manage signals to see the full collection and restore hidden profiles. The image signal is always shown as a profile.",
  windows:
    "Name the signal and enter one or more m/z intervals, or draw them on the spectrum. Overlapping intervals are counted once. Select a numbered interval to edit it; drag its edges to resize or Shift-drag it to move. Choose the first and last frames to calculate, then select Calculate signal or Update signal. Existing results stay in place until the calculation succeeds. Discard closes the draft without applying it. Stored signals and signals calculated from raw data may differ because the instrument processes them differently.",
  depth:
    "Choose the frames to display: all available frames, a single frame, or a range. In 3D, choose all frames or a range. In Explore, the ion map sums the selected frames. Enter a range and select Apply, or use the front projection or depth profile to select frames. Axis units switches between frame numbers and calibrated physical depth; add a depth calibration to use physical depth.",
  saving:
    "Save as writes your signals, results and settings to a new HDF5 copy. Choose folder selects where to save it. Finish or discard signal drafts before saving. Saved means the analysis matches its saved copy; Unsaved changes means it has changed since the last save. Open the copy to restore the analysis. The original file stays unchanged.",
  ion: "The ion map shows the selected signal summed over the viewing frames. Draw a rectangle to choose the region used for the depth profile and front projection. Drag its gold edges to resize it, or Shift-drag to move it. ROI lets you enter pixel coordinates. Display… changes the image, colors and scale without changing the data. PNG saves the image, and maximize enlarges the plot.",
  se: "The secondary electron (SE) image is shown in its original pixels and is not aligned with the SIMS image. For a range of frames, it shows the average of the available SE images. The selected SIMS region and front projection remain unchanged. Use Display… to switch images or change the display scale.",
  spectrum:
    "This is the spectrum stored in the file. Drag to zoom, or double-click to reset. When creating a signal, drag to select its m/z interval instead; the existing plots stay unchanged until the signal is calculated. Log y changes the display scale and omits zero values. Ctrl/Cmd-wheel zooms; ordinary wheel scrolling moves the page.",
  front:
    "The front projection shows the selected SIMS signal across the image and through the acquisition frames, summed over the selected region’s vertical extent. Click to select a frame, or drag vertically to select a range. Drag the range edges to resize it, or Shift-drag to move it. Blank areas indicate missing data. The projection remains SIMS when the SE image is displayed.",
  profile:
    "Each curve shows the mean signal per pixel in the selected region at each frame. Select a curve name for details, or × to hide it; use Manage signals to show it again. The image signal is always included. Relative profiles scales each curve to its own maximum for display only. Click to select a frame or drag to select a range. CSV exports the profile data.",
};
