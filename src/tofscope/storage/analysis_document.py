"""Bounded, versioned analysis state, independent of service identities and plots."""
from dataclasses import replace
import json
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

import h5py
import numpy as np
from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from tofscope.application.commands import StrictModel, DepthSelection, AnchorInput
from tofscope.science.depth_calibration import DepthAnchor, validate_anchors
from tofscope.application.models import AnalysisSnapshot, DisplaySettings, SignalSnapshot
from tofscope.science.signals import SignalRecipe

FiniteStrictFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]

ROOT = 'ToFScope/Analysis'
MAX_DOCUMENT_BYTES = 1024 * 1024


def canonical_id(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError('Document identifiers must be canonical UUIDs.')
    return value


class RecipeDocument(StrictModel):
    schema_version: Literal[3] = 3
    id: str
    label: str
    source: Literal['stored', 'custom']
    stored_index: StrictInt | None = None
    saved_id: None = None
    intervals: tuple[tuple[FiniteStrictFloat, FiniteStrictFloat], ...] = Field(min_length=1, max_length=128)
    frames: tuple[StrictInt, StrictInt]

    @model_validator(mode='after')
    def recipe_valid(self):
        SignalRecipe.from_dict(self.model_dump())
        return self


class DocumentSignal(StrictModel):
    id: str
    name: str = Field(min_length=1, max_length=128)
    style_index: StrictInt = Field(ge=0)
    recipe: RecipeDocument
    materialization_id: str | None = None

    @field_validator('id', 'materialization_id')
    @classmethod
    def identifiers(cls, value):
        return canonical_id(value) if value is not None else None

    @model_validator(mode='after')
    def materialization(self):
        if not self.name.strip():
            raise ValueError('Signal name cannot be blank.')
        if (self.recipe.source == 'custom') != (self.materialization_id is not None):
            raise ValueError('Custom signals require persisted result references.')
        return self


class DocumentDisplay(StrictModel):
    log: StrictBool = True
    relative: StrictBool = True
    image: Literal['sims', 'se'] = 'sims'
    spectrum_log: StrictBool = True
    colormap: Literal["ion", "gray", "viridis", "magma", "cividis"] = "viridis"


class SavedAnalysisDocument(StrictModel):
    schema_version: Literal[1, 2] = 2
    shape: tuple[StrictInt, StrictInt, StrictInt, StrictInt]
    signals: tuple[DocumentSignal, ...] = Field(min_length=1, max_length=129)
    image_signal_id: str
    profile_signal_ids: tuple[str, ...] = Field(max_length=129)
    next_style_index: StrictInt = Field(ge=0)
    loaded_frames: tuple[StrictInt, StrictInt]
    roi: tuple[StrictInt, StrictInt, StrictInt, StrictInt]
    depth: DepthSelection
    display: DocumentDisplay
    depth_anchors: tuple[AnchorInput, ...] = Field(default=(AnchorInput(frame=0, depth_nm=0.),), min_length=1, max_length=4096)
    depth_unit: Literal['nm', 'um', 'mm'] = 'nm'
    depth_coordinates: Literal['frame', 'depth'] = 'frame'

    @model_validator(mode='after')
    def relationships(self):
        nz, ny, nx, channels = self.shape
        if min(self.shape) <= 0:
            raise ValueError('Invalid saved acquisition dimensions.')
        anchors = tuple(DepthAnchor(x.frame, x.depth_nm) for x in self.depth_anchors)
        if anchors != validate_anchors(anchors, nz):
            raise ValueError('Saved calibration must include sorted anchors and fixed origin.')
        if self.depth_coordinates == 'depth' and len(anchors) < 2:
            raise ValueError('Saved physical coordinates require positive anchors.')
        ids = {s.id for s in self.signals}
        if len(ids) != len(self.signals) or self.image_signal_id not in ids:
            raise ValueError('Invalid saved signal relationships.')
        if len(set(self.profile_signal_ids)) != len(self.profile_signal_ids) or not set(self.profile_signal_ids) <= ids:
            raise ValueError('Invalid saved profile references.')
        if len({s.style_index for s in self.signals}) != len(self.signals) or self.next_style_index <= max(s.style_index for s in self.signals):
            raise ValueError('Invalid saved color ordinals.')
        first, last = self.loaded_frames
        x0, x1, y0, y1 = self.roi
        if not 0 <= first <= last < nz or not (0 <= x0 <= x1 < nx and 0 <= y0 <= y1 < ny):
            raise ValueError('Saved selection outside acquisition.')
        for row in self.signals:
            a, b = row.recipe.frames
            if not 0 <= a <= b < nz or (row.recipe.source == 'stored' and not 0 <= row.recipe.stored_index < channels):
                raise ValueError('Saved signal coverage/channel outside acquisition.')
        image = next(row for row in self.signals if row.id == self.image_signal_id)
        lo, hi = max(first, image.recipe.frames[0]), min(last, image.recipe.frames[1])
        if lo > hi:
            raise ValueError('Saved image has no coverage in analysis range.')
        if self.depth.mode == 'frame' and not lo <= self.depth.index <= hi:
            raise ValueError('Saved viewing frame outside coverage.')
        if self.depth.mode == 'window' and not lo <= self.depth.first <= self.depth.last <= hi:
            raise ValueError('Saved viewing window outside coverage.')
        return self


def encode_document(snapshot: AnalysisSnapshot) -> SavedAnalysisDocument:
    rows = []
    for row in snapshot.signals:
        if row.recipe is None:
            raise ValueError('Finish or discard pending signals before saving.')
        rows.append(dict(id=row.id, name=row.name, style_index=row.style_index,
                         recipe=row.recipe.to_dict(), materialization_id=(row.materialization_id or str(uuid4())) if row.recipe.source == 'custom' else None))
    return SavedAnalysisDocument(shape=snapshot.shape, signals=rows,
        image_signal_id=snapshot.image_signal_id, profile_signal_ids=snapshot.profile_signal_ids,
        next_style_index=snapshot.next_style_index, loaded_frames=snapshot.loaded_frames,
        roi=snapshot.roi, depth=snapshot.depth, display=vars(snapshot.display), depth_anchors=[vars(x) for x in snapshot.depth_anchors],
        depth_unit=snapshot.depth_unit, depth_coordinates=snapshot.depth_coordinates)


def read_document(path: Path, limits) -> SavedAnalysisDocument | None:
    try:
        with h5py.File(path, 'r') as handle:
            if ROOT not in handle:
                return None
            group = handle[ROOT]
            if not isinstance(group, h5py.Group) or group.attrs.get('schema_version') not in (1, 2) or group.attrs.get('complete') != np.bool_(True):
                raise ValueError('Unsupported or incomplete saved analysis.')
            data = group['state_json']
            if not isinstance(data, h5py.Dataset) or data.ndim != 1 or data.dtype != np.uint8 or not 0 < data.size <= min(MAX_DOCUMENT_BYTES, limits.response_bytes):
                raise ValueError('Saved analysis metadata exceeds limits or has invalid encoding.')
            value = SavedAnalysisDocument.model_validate(json.loads(data[:].tobytes()))
            if value.schema_version != group.attrs['schema_version']:
                raise ValueError('Saved document version mismatch.')
            if len(value.signals) > limits.signals_per_analysis:
                raise ValueError('Saved signal count exceeds this service limit.')
            if value.shape != tuple(handle['PeakData/PeakData'].shape):
                raise ValueError('Saved analysis dimensions differ from acquisition.')
            return value
    except (KeyError, TypeError, OSError, UnicodeError, RecursionError) as exc:
        raise ValueError('Saved analysis metadata is invalid.') from exc


def restore_snapshot(document: SavedAnalysisDocument, initial: AnalysisSnapshot) -> AnalysisSnapshot:
    if document.shape != initial.shape or (document.display.image == 'se' and not initial.has_se):
        raise ValueError('Saved analysis does not match acquisition metadata.')
    ids = {s.id: str(uuid4()) for s in document.signals}
    rows = []
    for row in document.signals:
        recipe = SignalRecipe.from_dict(row.recipe.model_dump())
        recipe = replace(recipe, id=str(uuid4()))
        rows.append(SignalSnapshot(ids[row.id], row.name, row.style_index, recipe,
                                   materialization_id=row.materialization_id))
    return replace(initial, signals=tuple(rows), image_signal_id=ids[document.image_signal_id],
        profile_signal_ids=tuple(ids[x] for x in document.profile_signal_ids),
        next_style_index=document.next_style_index, loaded_frames=document.loaded_frames,
        roi=document.roi, depth=document.depth, display=DisplaySettings(**document.display.model_dump()), saved_revision=initial.revision,
        depth_anchors=tuple(DepthAnchor(x.frame, x.depth_nm) for x in document.depth_anchors),
        depth_unit=document.depth_unit, depth_coordinates=document.depth_coordinates)
