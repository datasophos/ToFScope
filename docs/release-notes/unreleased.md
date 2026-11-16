
The front projection now crops to the selected ROI’s horizontal bounds while retaining the original coordinates, so it and the depth profile represent the same region (fix for [#26](https://github.com/datasophos/ToFScope/issues/26)).

The front projection can now switch between XZ and YZ views, so you can inspect either spatial axis through the selected region.

ToFScope now calculates a mass spectrum from raw detection events for the selected region and frames, with a progress bar, cancellation, and a way to return to the total sum spectrum. An out-of-date notice indicates when the selection no longer matches the displayed spectrum.

The mass spectrum toolbar now groups analysis tools in an Analyze menu and uses a Total sum / ROI switch. ROI calculation is disabled when the selected region and frames have already been calculated.

Documentation screenshots now show a reproducible synthetic device with layered signals and spatial features.

Added CSV export for the displayed total sum or ROI mass spectrum, with acquisition and selection details in the header.
