"""Validate editable zone rules before they can interrupt a stream worker."""
from datetime import time
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Coordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Schedule(BaseModel):
    model_config = ConfigDict(extra='forbid')
    days: list[Annotated[int, Field(ge=0, le=6, strict=True)]] = Field(min_length=1, max_length=7)
    start: str = Field(pattern=r'^\d{2}:\d{2}$')
    end: str = Field(pattern=r'^\d{2}:\d{2}$')

    @field_validator('start', 'end')
    @classmethod
    def valid_time(cls, value):
        time.fromisoformat(value)
        return value


class Rule(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    type: Literal['crowding', 'queue_build_up', 'restricted_entry', 'after_hours_entry',
                  'loitering', 'unattended_object', 'blocked_exit']
    threshold: int = Field(default=0, ge=0, le=10000, strict=True)
    durationSeconds: float = Field(default=0, ge=0, le=86400)
    radius: float = Field(default=.15, gt=0, le=1)
    movementTolerance: float = Field(default=.02, gt=0, le=1)
    timezone: str = Field(default='UTC', max_length=80)
    allowedHours: list[Schedule] = Field(default_factory=list, max_length=14)

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError('Unknown schedule timezone') from exc
        return value


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def intersect(a, b, c, d):
    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]):
        return False
    if max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
        return False
    return cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0


class Zone(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=80)
    polygon: list[tuple[Coordinate, Coordinate]] = Field(min_length=3, max_length=64)
    rules: list[Rule] = Field(default_factory=list, max_length=16)

    @model_validator(mode='after')
    def valid_polygon(self):
        points = self.polygon
        if len(set(points)) != len(points):
            raise ValueError('Polygon vertices must be distinct')
        edges = list(zip(points, points[1:] + points[:1]))
        if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) < 1e-8:
            raise ValueError('Polygon must have nonzero area')
        for i, (a, b) in enumerate(edges):
            for j, (c, d) in enumerate(edges):
                if j <= i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                if intersect(a, b, c, d):
                    raise ValueError('Polygon edges must not cross or touch')
        if len({rule.type for rule in self.rules}) != len(self.rules):
            raise ValueError('Use one rule of each type per zone')
        return self


def validate_detection_config(value):
    if value is None:
        return value
    zones = value.get('zones', [])
    if not isinstance(zones, list) or len(zones) > 32:
        raise ValueError('Use at most 32 zones per source')
    validated = [Zone.model_validate(zone) for zone in zones]
    if len({zone.id for zone in validated}) != len(validated):
        raise ValueError('Zone names must be unique per source')
    return value
