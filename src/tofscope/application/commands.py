from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictBool, TypeAdapter


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AllDepth(StrictModel):
    mode: Literal["all"] = "all"


class SingleFrame(StrictModel):
    mode: Literal["frame"]
    index: StrictInt


class DepthWindow(StrictModel):
    mode: Literal["window"]
    first: StrictInt
    last: StrictInt


DepthSelection = Annotated[
    Union[AllDepth, SingleFrame, DepthWindow], Field(discriminator="mode")
]


class AddStoredSignal(StrictModel):
    type: Literal['add_stored_signal']
    index: StrictInt
    duplicate: StrictBool = False
    frames: tuple[StrictInt, StrictInt] | None = None


class SignalId(StrictModel):
    signal_id: str


class RenameSignal(SignalId):
    type: Literal['rename_signal']
    name: str


class SelectImageSignal(SignalId):
    type: Literal['select_image_signal']


class SetProfileVisible(SignalId):
    type: Literal['set_profile_visible']
    visible: StrictBool


class RemoveSignal(SignalId):
    type: Literal['remove_signal']


class SetStoredCoverage(SignalId):
    type: Literal['set_stored_coverage']
    frames: tuple[StrictInt, StrictInt]


class SetROI(StrictModel):
    type: Literal["set_roi"]
    roi: tuple[StrictInt, StrictInt, StrictInt, StrictInt]


class SetDepth(StrictModel):
    type: Literal["set_depth"]
    depth: DepthSelection


class SetAnalysisFrames(StrictModel):
    type: Literal['set_analysis_frames']
    frames: tuple[StrictInt, StrictInt]


class SetDisplay(StrictModel):
    type: Literal["set_display"]
    log: StrictBool
    relative: StrictBool
    image: Literal["sims", "se"] = "sims"
    spectrum_log: StrictBool | None = None
    colormap: Literal["ion", "gray", "viridis", "magma", "cividis"] | None = None


class AnchorInput(StrictModel):
    frame: StrictInt
    depth_nm: Annotated[float, Field(strict=True, allow_inf_nan=False)]


class SetDepthAnchors(StrictModel):
    type: Literal['set_depth_anchors']
    anchors: tuple[AnchorInput, ...] = Field(max_length=4096)


class SetDepthDisplay(StrictModel):
    type: Literal['set_depth_display']
    unit: Literal['nm', 'um', 'mm']
    coordinates: Literal['frame', 'depth']


Command = Annotated[
    Union[
        AddStoredSignal,
        RenameSignal,
        SelectImageSignal,
        SetProfileVisible,
        RemoveSignal,
        SetStoredCoverage,
        SetROI,
        SetDepth,
        SetAnalysisFrames,
        SetDisplay,
        SetDepthAnchors,
        SetDepthDisplay,
    ],
    Field(discriminator="type"),
]
command_adapter = TypeAdapter(Command)


class CommandEnvelope(StrictModel):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=0)
    dataset_generation: str = Field(min_length=1, max_length=128)
    command: Command

    def __init__(self, *args, **kwargs):
        if args:
            kwargs = (
                dict(
                    zip(
                        (
                            "request_id",
                            "expected_revision",
                            "dataset_generation",
                            "command",
                        ),
                        args,
                    )
                )
                | kwargs
            )
        super().__init__(**kwargs)
