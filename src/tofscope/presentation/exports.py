from dataclasses import dataclass
from contextlib import ExitStack
import csv
import numpy as np
from tofscope.presentation.coordinates import calibration
import io
import json
from tofscope.presentation.explore import selected_frames
from dataclasses import asdict
from tofscope.application.identification import current_result
from tofscope.application.signals import visible_signals


@dataclass(frozen=True)
class Download:
    filename: str
    media_type: str
    content: bytes


class ExportService:
    def __init__(self, presenter):
        self.presenter = presenter

    def render(self, owner, analysis_id, format):
        p = self.presenter
        e = p.analyses.entry(owner, analysis_id)
        with e.lock:
            s = e.snapshot
            p.repository.assert_current(owner, s.dataset)
            if format == "json":
                value = dict(
                    schema_version=4,
                    signals=[asdict(row) for row in s.signals if row.recipe is not None],
                    image_signal_id=s.image_signal_id,
                    profile_signal_ids=list(s.profile_signal_ids),
                    scope="Explore",
                    isotope_measurement=asdict(current_result(s)) if s.isotope_measurement else None,
                    relative_path=s.dataset.relative_path,
                    dataset_generation=s.dataset.generation,
                    selected_frames=list(selected_frames(s)),
                    depth=s.depth.model_dump(),
                    roi=list(s.roi),
                    calibration={
                        "anchors_nm": [[x.frame, x.depth_nm] for x in s.depth_anchors],
                        "unit": s.depth_unit,
                        "coordinates": s.depth_coordinates,
                        "extrapolation": False,
                        "policy": "interpolate only between anchors",
                    },
                    display={
                        "log": s.display.log,
                        "relative": s.display.relative,
                        "image": s.display.image,
                        "spectrum_log": s.display.spectrum_log,
                        "colormap": s.display.colormap,
                    },
                    recipe_import_available=False,
                )
                content = json.dumps(value, allow_nan=False, indent=2).encode()
                media = "application/json"
            elif format == "csv":
                with ExitStack() as stack:
                    estimate = s.shape[0] * (
                        len(visible_signals(s)) + 1
                    ) * 128 + len(s.depth_anchors) * 256 + 4096
                    if estimate > p.settings.response_bytes:
                        raise ValueError("Export exceeds configured response limit.")
                    stack.enter_context(
                        p.cache.budget.reserve(owner, analysis_id, estimate)
                    )
                    curves = p.curves(s, stack)
                    out = io.StringIO()
                    writer = csv.writer(out)
                    depth_calibration = calibration(s)
                    writer.writerow(["frame", *(["depth_nm"] if depth_calibration else []), *[c.label for c in curves]])
                    first, last = (
                        (s.depth.first, s.depth.last)
                        if s.depth.mode == "window"
                        else (0, s.shape[0] - 1)
                    )
                    depths = depth_calibration.frame_to_depth(np.arange(first, last + 1)) if depth_calibration else None
                    for offset, z in enumerate(range(first, last + 1)):
                        writer.writerow(
                            [
                                z,
                                *([float(depths[offset]) if np.isfinite(depths[offset]) else ''] if depths is not None else []),
                                *[
                                    ""
                                    if c.values[z] is None
                                    else c.values[z]
                                    for c in curves
                                ],
                            ]
                        )
                    content = out.getvalue().encode()
                    media = "text/csv"
            else:
                raise ValueError("Unknown export format.")
            p.repository.assert_current(owner, s.dataset)
            return Download(f"tofscope-{analysis_id}.{format}", media, content)
