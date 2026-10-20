from typing import Literal, Annotated
from pydantic import Field, StrictInt, StrictBool
from tofscope.application.commands import StrictModel


class OpenAcquisition(StrictModel):
    relative_path: str = Field(min_length=1, max_length=4096)
    location: Literal["acquisition", "saved"] = "acquisition"


class PrepareAcquisition(OpenAcquisition):
    generation: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=240)
    accept_assumptions: StrictBool = False


class RevisionEnvelope(StrictModel):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=0)
    dataset_generation: str = Field(min_length=1, max_length=128)


class ReplaceAcquisition(RevisionEnvelope):
    relative_path: str = Field(min_length=1, max_length=4096)
    location: Literal["acquisition", "saved"] = "acquisition"


FiniteStrictFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class IntegrationInput(StrictModel):
    intervals: list[tuple[FiniteStrictFloat, FiniteStrictFloat]] = Field(
        min_length=1, max_length=128
    )
    frames: tuple[StrictInt, StrictInt]
    name: str = Field(min_length=1, max_length=128)
    signal_id: str | None = None
    expected_recipe_version: StrictInt | None = Field(default=None, ge=0)


class SubmitJob(RevisionEnvelope):
    spec: IntegrationInput


class Bootstrap(StrictModel):
    secret: str = Field(max_length=256)


class SessionInfo(StrictModel):
    owner: str
    csrf: str
    initial_file: str | None = None


class ErrorResponse(StrictModel):
    code: str
    message: str
    request_id: str | None = None
    current_revision: int | None = None


class SaveCopy(RevisionEnvelope):
    filename: str = Field(min_length=1, max_length=240)


class FolderLocations(StrictModel):
    acquisitions: str
    saved_copies: str
    save_destination: str
