from typing import Literal
from pydantic import Field,StrictInt,FiniteFloat
from tofscope.application.commands import StrictModel,CommandEnvelope

class OpenAcquisition(StrictModel):relative_path:str=Field(min_length=1,max_length=4096)
class RevisionEnvelope(StrictModel):
    request_id:str=Field(min_length=1,max_length=128)
    expected_revision:StrictInt=Field(ge=0)
    dataset_generation:str=Field(min_length=1,max_length=128)
class ReplaceAcquisition(RevisionEnvelope):relative_path:str=Field(min_length=1,max_length=4096)
class IntegrationInput(StrictModel):
    intervals:list[tuple[FiniteFloat,FiniteFloat]]=Field(min_length=1,max_length=128)
    frames:tuple[StrictInt,StrictInt]
    target:Literal['active','comparison']
class SubmitJob(RevisionEnvelope):spec:IntegrationInput
class Bootstrap(StrictModel):secret:str=Field(max_length=256)
class SessionInfo(StrictModel):owner:str;csrf:str
class ErrorResponse(StrictModel):
    code:str
    message:str
    request_id:str|None=None
    current_revision:int|None=None
