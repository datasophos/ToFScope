from dataclasses import dataclass, field, asdict
from typing import Literal


@dataclass(frozen=True)
class Axis:
    name: str
    unit: str
    values: list[float]
    boundaries: list[float]


@dataclass(frozen=True)
class Curve:
    signal_id: str
    style_index: int
    label: str
    values: list[float | None]
    coverage: list[bool]


@dataclass(frozen=True)
class Panel:
    kind: Literal["image", "line"]
    content_version: str
    axes: list[Axis]
    values: list[list[float | None]] = field(default_factory=list)
    coverage: list[list[bool]] = field(default_factory=list)
    series: list[Curve] = field(default_factory=list)
    units: str = "intensity"
    aggregation: str = "original"
    intensity_range: tuple[float, float] = (0, 1)
    palette: Literal["ion", "gray", "viridis", "magma", "cividis"] = "viridis"
    log: bool = False
    relative: bool = False
    signal_id: str | None = None
    signal_name: str | None = None
    signal_version: int | None = None
    frame_range: tuple[int, int] | None = None
    acquisition_frames: list[int] = field(default_factory=list)
    omitted_frames: int = 0
    coordinate_kind: Literal['frame', 'depth'] = 'frame'



@dataclass(frozen=True)
class ExploreData:
    analysis_id: str
    revision: int
    dataset_generation: str
    panels: dict[str, Panel]

    def to_dict(self):
        return asdict(self)
