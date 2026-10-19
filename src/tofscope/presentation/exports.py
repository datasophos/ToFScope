from dataclasses import dataclass
from contextlib import ExitStack
import csv
import io
import json
from tofscope.presentation.explore import selected_frames
from dataclasses import asdict
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
        e = p.workspaces.entry(owner, analysis_id)
        with e.lock:
            s = e.snapshot
            p.repository.assert_current(owner, s.dataset)
            if format == "json":
                value = dict(
                    schema_version=4,
                    signals=[asdict(row) for row in s.signals if row.recipe is not None],
                    image_signal_id=s.image_signal_id,
                    profile_signal_ids=list(s.profile_signal_ids),
                    scope="Explore-only",
                    relative_path=s.dataset.relative_path,
                    dataset_generation=s.dataset.generation,
                    loaded_frames=list(s.loaded_frames),
                    selected_frames=list(selected_frames(s)),
                    depth=s.depth.model_dump(),
                    roi=list(s.roi),
                    calibration={
                        "anchors_nm": [[0, 0]],
                        "policy": "interpolate only between anchors",
                    },
                    display={
                        "log": s.display.log,
                        "relative": s.display.relative,
                        "image": s.display.image,
                    },
                    recipe_import_available=False,
                )
                content = json.dumps(value, allow_nan=False, indent=2).encode()
                media = "application/json"
            elif format == "csv":
                with ExitStack() as stack:
                    estimate = (s.loaded_frames[1] - s.loaded_frames[0] + 1) * (
                        len(visible_signals(s))
                    ) * 128 + 4096
                    if estimate > p.settings.response_bytes:
                        raise ValueError("Export too large; narrow loaded frames.")
                    stack.enter_context(
                        p.cache.budget.reserve(owner, analysis_id, estimate)
                    )
                    curves = p.curves(s, stack)
                    out = io.StringIO()
                    writer = csv.writer(out)
                    writer.writerow(["frame", *[c.label for c in curves]])
                    first, last = (
                        (s.depth.first, s.depth.last)
                        if s.depth.mode == "window"
                        else s.loaded_frames
                    )
                    for z in range(first, last + 1):
                        writer.writerow(
                            [
                                z,
                                *[
                                    ""
                                    if c.values[z - s.loaded_frames[0]] is None
                                    else c.values[z - s.loaded_frames[0]]
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
