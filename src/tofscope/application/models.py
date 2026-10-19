from dataclasses import dataclass
from tofscope.storage.acquisitions import DatasetRef
from tofscope.science.signals import SignalRecipe
from tofscope.application.commands import DepthSelection,AllDepth

@dataclass(frozen=True)
class DisplaySettings:
    log: bool=False
    relative: bool=False
    image: str='sims'
@dataclass(frozen=True)
class Peak:
    index:int
    label:str
    mass:float
    low:float
    high:float
@dataclass(frozen=True)
class WorkspaceSnapshot:
    id:str
    owner:str
    analysis_ids:tuple[str,...]=()
@dataclass(frozen=True)
class AnalysisSnapshot:
    id:str
    owner:str
    workspace_id:str
    dataset:DatasetRef
    revision:int
    loaded_frames:tuple[int,int]
    roi:tuple[int,int,int,int]
    depth:DepthSelection
    active_recipe:SignalRecipe
    comparisons:tuple[SignalRecipe,...]
    display:DisplaySettings
    shape:tuple[int,int,int,int]
    peaks:tuple[Peak,...]
    fov_um:float|None
    mass_limits:tuple[float,float]
    stale:bool=False
