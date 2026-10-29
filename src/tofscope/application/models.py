from tofscope.application.spatial import SpatialView
from tofscope.application.identification_models import AtomicAssignment, MeasurementResult
from dataclasses import dataclass
from typing import Literal
from tofscope.science.depth_calibration import DepthAnchor
from tofscope.storage.acquisitions import DatasetRef
from tofscope.science.signals import SignalRecipe
from tofscope.application.commands import DepthSelection


@dataclass(frozen=True)
class DisplaySettings:
    log: bool = True
    relative: bool = True
    image: str = "sims"
    spectrum_log: bool = True
    colormap: Literal["ion", "gray", "viridis", "magma", "cividis"] = "viridis"


    def __post_init__(self):
        # Saved analyses and older clients may still use the retired palette name.
        if self.colormap == "ion":
            object.__setattr__(self, "colormap", "viridis")


@dataclass(frozen=True)
class Peak:
    index: int
    label: str
    mass: float
    low: float
    high: float


@dataclass(frozen=True)
class SignalSnapshot:
    id: str
    name: str
    style_index: int
    recipe: SignalRecipe | None
    recipe_version: int = 1
    name_revision: int = 0
    job_id: str | None = None
    materialization_id: str | None = None
    assignment: AtomicAssignment | None = None


@dataclass(frozen=True)
class AnalysisSnapshot:
    id: str
    owner: str
    dataset: DatasetRef
    revision: int
    roi: tuple[int, int, int, int]
    depth: DepthSelection
    signals: tuple[SignalSnapshot, ...]
    image_signal_id: str
    profile_signal_ids: tuple[str, ...]
    next_style_index: int
    display: DisplaySettings
    shape: tuple[int, int, int, int]
    peaks: tuple[Peak, ...]
    fov_um: float | None
    mass_limits: tuple[float, float]
    stale: bool = False
    has_se: bool = False
    saved_revision: int | None = None
    opened_revision: int = 0
    depth_anchors: tuple[DepthAnchor, ...] = (DepthAnchor(0, 0.),)
    depth_unit: Literal['nm', 'um', 'mm'] = 'nm'
    depth_coordinates: Literal['frame', 'depth'] = 'frame'
    isotope_measurement: MeasurementResult | None = None
    isotope_job_id: str | None = None
    spatial: SpatialView = SpatialView()
