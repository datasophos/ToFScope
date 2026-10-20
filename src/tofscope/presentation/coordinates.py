"""Reusable, sample-preserving depth geometry for Explore and later spatial views.

Coordinates describe original acquisition samples, never a resampled intensity grid.
Unknown physical depths are omitted from physical views, but retained by CSV exports.
Cell boundaries are display footprints, not measurements of plane thickness.
"""
import numpy as np
from tofscope.science.depth_calibration import DepthCalibration, convert_depth


def calibration(snapshot):
    return DepthCalibration(snapshot.depth_anchors, snapshot.shape[0]) if len(snapshot.depth_anchors) > 1 else None


def depth_samples(snapshot):
    frames = np.arange(snapshot.loaded_frames[0], snapshot.loaded_frames[1] + 1)
    active = calibration(snapshot) if snapshot.depth_coordinates == 'depth' else None
    if active is None:
        return frames, frames.astype(float), 'frame', 0
    depths = active.frame_to_depth(frames)
    known = np.isfinite(depths)
    return frames[known], convert_depth(depths[known], 'nm', snapshot.depth_unit), ('µm' if snapshot.depth_unit == 'um' else snapshot.depth_unit), int((~known).sum())


def block_depths(snapshot, frame_blocks):
    """Mean each block's calibrated samples, including anchor slope changes.

    A block containing unknown samples is invalid: callers must clip before pooling.
    """
    active = calibration(snapshot)
    return [float(np.mean(active.frame_to_depth(block))) for block in frame_blocks]
