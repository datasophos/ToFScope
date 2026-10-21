"""Validate captured measurements before treating persisted metadata as current."""
import math


def validate_measurement(document):
    result = document.isotope_measurement
    if result is None:
        return
    nz, ny, nx, _ = document.shape
    x0, x1, y0, y1 = result.roi
    first, last = result.frames
    if not (0 <= x0 <= x1 < nx and 0 <= y0 <= y1 < ny and 0 <= first <= last < nz):
        raise ValueError('Captured measurement scope outside acquisition.')
    ids = [row.signal_id for row in result.rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate measured signal.')
    for row in result.rows:
        m = row.measurement
        if m.requested_frames != result.frames:
            raise ValueError('Inconsistent requested measurement coverage.')
        if not row.intervals or len(row.intervals) > 128 or any(not (math.isfinite(a) and math.isfinite(b) and a < b) for a, b in row.intervals):
            raise ValueError('Invalid captured mass intervals.')
        if m.actual_frames is None:
            if m.summed_intensity is not None or m.observed_fraction is not None:
                raise ValueError('Uncovered measurement must remain unavailable.')
        elif not (first <= m.actual_frames[0] <= m.actual_frames[1] <= last):
            raise ValueError('Invalid actual measurement coverage.')
        elif m.summed_intensity is None or not math.isfinite(m.summed_intensity):
            raise ValueError('Invalid captured intensity.')
        if m.observed_fraction is not None and (m.ambiguous or not math.isfinite(m.observed_fraction) or not 0 <= m.observed_fraction <= 1):
            raise ValueError('Invalid captured fraction.')
    if result.out_of_date:
        return
    depth = document.depth
    frames = ((depth.index, depth.index) if depth.mode == 'frame' else
              (depth.first, depth.last) if depth.mode == 'window' else (0, nz - 1))
    signals = {row.id: row for row in document.signals}
    if result.roi != document.roi or result.frames != frames or not set(ids) <= signals.keys():
        raise ValueError('Current measurement does not match saved selection.')
    common = (max(first, *(signals[sid].recipe.frames[0] for sid in ids)),
              min(last, *(signals[sid].recipe.frames[1] for sid in ids)))
    actual = common if common[0] <= common[1] else None
    for row in result.rows:
        signal = signals[row.signal_id]
        if (row.intervals != signal.recipe.intervals or row.assignment != signal.assignment or
                row.measurement.recipe_id != signal.recipe.id or row.measurement.actual_frames != actual):
            raise ValueError('Current measurement does not match saved signals.')
