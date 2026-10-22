"""Validated, durable spatial display state; numerical recipes remain signals."""

from typing import Annotated, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class SpatialModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Vector(SpatialModel):
    x: Number
    y: Number
    z: Number


class Camera(SpatialModel):
    eye: Vector = Vector(x=1.25, y=1.25, z=1.25)
    center: Vector = Vector(x=0.0, y=0.0, z=0.0)
    up: Vector = Vector(x=0.0, y=0.0, z=1.0)
    projection: Literal["perspective", "orthographic"] = "perspective"

    @model_validator(mode="after")
    def nondegenerate(self):
        if sum(v * v for v in (self.up.x, self.up.y, self.up.z)) < 1e-12:
            raise ValueError("Camera up vector must be nonzero.")
        if sum(v * v for v in (self.eye.x, self.eye.y, self.eye.z)) < 1e-12:
            raise ValueError("Camera eye must be nonzero.")
        return self


class SpatialLayer(SpatialModel):
    signal_id: str = Field(min_length=1, max_length=128)
    visible: StrictBool = True
    colorscale: Literal[
        "Viridis", "Magma", "Plasma", "Cividis", "Reds", "Blues", "Greens", "Purples"
    ] = "Viridis"
    opacity: Number = Field(default=0.12, ge=0, le=1)
    percentile: Number = Field(default=70.0, ge=0, le=100)
    camera: Camera = Camera()


class SpatialView(SpatialModel):
    screen: Literal["explore", "volume"] = "explore"
    layers: tuple[SpatialLayer, ...] = Field(default=(), max_length=129)
    mode: Literal["overlay", "tiles"] = "overlay"
    quality: Literal["Fast", "Detailed"] = "Fast"
    scale: Literal["independent", "shared"] = "independent"
    linked: StrictBool = True
    camera: Camera = Camera()
    solo: str | None = Field(default=None, max_length=128)
    page: StrictInt = Field(default=0, ge=0, le=128)
    frame_stretch: Number = Field(default=1.2, ge=0.01, le=1000)
    depth_exaggeration: Number = Field(default=1.0, ge=0.01, le=1000)

    @model_validator(mode="after")
    def references(self):
        ids = [x.signal_id for x in self.layers]
        if len(ids) != len(set(ids)) or self.solo is not None and self.solo not in ids:
            raise ValueError("Invalid spatial layer references.")
        return self


def validate_spatial(spatial, signals):
    ready = {s.id for s in signals if s.recipe is not None}
    if not {x.signal_id for x in spatial.layers} <= ready:
        raise ValueError("Spatial layers must reference ready named signals.")
    return spatial
