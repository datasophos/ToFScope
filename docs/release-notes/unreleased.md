
The front projection now crops to the selected ROI’s horizontal bounds while retaining the original coordinates, so it and the depth profile represent the same region (fix for [#26](https://github.com/datasophos/ToFScope/issues/26)).

The front projection can now switch between XZ and YZ views, so you can inspect either spatial axis through the selected region.

ToFScope now calculates a mass spectrum from raw detection events for the selected region and frames, with progress, cancellation, and a way to return to the acquisition-wide spectrum.
