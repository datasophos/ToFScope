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


class SelectStored(StrictModel):
    type: Literal["select_stored"]
    index: StrictInt


class SetROI(StrictModel):
    type: Literal["set_roi"]
    roi: tuple[StrictInt, StrictInt, StrictInt, StrictInt]


class SetDepth(StrictModel):
    type: Literal["set_depth"]
    depth: DepthSelection


class SetLoadedFrames(StrictModel):
    type: Literal["set_loaded_frames"]
    frames: tuple[StrictInt, StrictInt]


class AddStoredComparison(StrictModel):
    type: Literal["add_stored_comparison"]
    index: StrictInt


class RemoveComparison(StrictModel):
    type: Literal["remove_comparison"]
    recipe_id: str


class SetDisplay(StrictModel):
    type: Literal["set_display"]
    log: StrictBool
    relative: StrictBool
    image: Literal["sims", "se"] = "sims"


Command = Annotated[
    Union[
        SelectStored,
        SetROI,
        SetDepth,
        SetLoadedFrames,
        AddStoredComparison,
        RemoveComparison,
        SetDisplay,
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
