"""Deterministic zone rules over fresh, tracked observations.

Times are monotonic seconds. Long gaps reset dwell; missing video must never
be counted as evidence that an object remained present.
"""
from dataclasses import dataclass, field
from datetime import datetime, time as clock_time
from math import hypot
from zoneinfo import ZoneInfo

import cv2
import numpy as np


@dataclass(frozen=True)
class Observation:
    track_id: int
    label: str
    x: float
    y: float
    confidence: float


@dataclass(frozen=True)
class ZoneRule:
    zone_id: str
    polygon: list[tuple[float, float]]
    kind: str
    threshold: int = 0
    duration: float = 0
    radius: float = .15
    movement_tolerance: float = .02
    timezone: str = 'UTC'
    allowed_hours: list[dict] = field(default_factory=list)
    # After an incident, wait this long before raising another for the same
    # zone rule (any person/group). Crowding/queue default to 120 s via config;
    # per-person rules default to 0 so every new person alerts.
    cooldown: float = 0

    def __post_init__(self):
        if self.kind not in {'crowding', 'queue_build_up', 'loitering', 'restricted_entry', 'blocked_exit', 'unattended_object', 'after_hours_entry'}:
            raise ValueError(f'Unsupported rule: {self.kind}')
        points = np.asarray(self.polygon, dtype=np.float32)
        if points.shape != (len(self.polygon), 2) or len(points) < 3:
            raise ValueError('Polygon needs at least three points')
        if not np.isfinite(points).all() or (points < 0).any() or (points > 1).any():
            raise ValueError('Polygon coordinates must be normalized')
        if cv2.contourArea(points) <= 0:
            raise ValueError('Polygon has no area')
        if not np.isfinite(self.cooldown) or self.cooldown < 0:
            raise ValueError('Cooldown must be nonnegative')
        if self.threshold < 0 or not np.isfinite(self.duration) or self.duration < 0:
            raise ValueError('Rule thresholds must be nonnegative')
        if not 0 < self.radius <= 1 or not 0 < self.movement_tolerance <= 1:
            raise ValueError('Distance thresholds must be normalized and positive')
        ZoneInfo(self.timezone)
        for window in self.allowed_hours:
            for key in ('start', 'end'):
                clock_time.fromisoformat(window[key])
            if not window['days'] or any(day not in range(7) for day in window['days']):
                raise ValueError('Schedule weekdays must be 0 (Monday) through 6')

    def is_after_hours(self, wall_time):
        local = datetime.fromtimestamp(wall_time, ZoneInfo(self.timezone))
        current = local.time().replace(tzinfo=None)
        for window in self.allowed_hours:
            start, end = (clock_time.fromisoformat(window[key]) for key in ('start', 'end'))
            if start < end:
                allowed = local.weekday() in window['days'] and start <= current < end
            else:
                allowed = (local.weekday() in window['days'] and current >= start) or (
                    (local.weekday() - 1) % 7 in window['days'] and current < end)
            if allowed:
                return False
        return True


class RuleEngine:
    def __init__(self, rules: list[ZoneRule], max_observation_gap=1.5, count_grace=1.5):
        self.rules = rules
        self.max_gap = max_observation_gap
        # Crowding/queue: a dense crowd's detected count flickers frame to frame;
        # a dip shorter than this does not restart the duration timer.
        self.count_grace = count_grace
        self.previous_time: float | None = None
        self.since: dict[tuple, float] = {}
        self.fired: set[tuple] = set()
        self.anchors = {}
        self.last_inside = {}
        self.last_aggregate_event: dict[int, float] = {}

    def update(self, now: float, observations: list[Observation], wall_time=None,
               counted: list[Observation] | None = None) -> list[dict]:
        """`observations` are tracked objects (per-person rules); `counted` are the
        frame's raw detections, used by crowding/queue rules because counting a
        dense crowd needs no identity and the tracker cannot confirm small,
        fast-moving people at a few frames per second. Defaults to observations."""
        counted = observations if counted is None else counted
        if self.previous_time is not None and (now - self.previous_time > self.max_gap or now < self.previous_time):
            self.since.clear()
            self.fired.clear()
            self.anchors.clear()
            self.last_inside.clear()
        self.previous_time = now
        present = set()
        events = []
        for index, rule in enumerate(self.rules):
            if rule.kind == 'after_hours_entry':
                if wall_time is None:
                    raise ValueError('After-hours rules require a wall-clock capture timestamp')
                if not rule.is_after_hours(wall_time):
                    continue
            polygon = np.asarray(rule.polygon, dtype=np.float32)
            inside = [o for o in observations if cv2.pointPolygonTest(polygon, (o.x, o.y), False) >= 0]
            people = [o for o in inside if o.label == 'person']
            if rule.kind in {'crowding', 'queue_build_up'}:
                crowd = [o for o in counted if o.label == 'person'
                         and cv2.pointPolygonTest(polygon, (o.x, o.y), False) >= 0]
                groups = [crowd] if len(crowd) > rule.threshold else []
            elif rule.kind == 'unattended_object':
                groups = []
                all_people = [o for o in observations if o.label == 'person']
                for obj in inside:
                    if obj.label not in {'backpack', 'handbag', 'suitcase'}:
                        continue
                    key = (index, obj.track_id)
                    anchor = self.anchors.get(key, (obj.x, obj.y))
                    moved = hypot(obj.x - anchor[0], obj.y - anchor[1]) > rule.movement_tolerance
                    attended = any(hypot(obj.x - p.x, obj.y - p.y) <= rule.radius for p in all_people)
                    if moved or attended:
                        self.since.pop(key, None)
                        self.fired.discard(key)
                        anchor = (obj.x, obj.y)
                    self.anchors[key] = anchor
                    if not attended:
                        groups.append([obj])
            elif rule.kind == 'blocked_exit':
                groups = [[o] for o in inside]
            else:
                groups = [[o] for o in people]
            for group in groups:
                aggregate = rule.kind in {'crowding', 'queue_build_up'}
                key = (index, None if aggregate else group[0].track_id)
                present.add(key)
                self.last_inside[key] = now
                since = self.since.setdefault(key, now)
                if now - since >= rule.duration and key not in self.fired:
                    self.fired.add(key)
                    if rule.cooldown > 0:
                        # One incident per zone rule per cooldown, whichever person or
                        # group triggers it; suppressed triggers stay "fired" so they
                        # re-arm only after the zone clears or the track leaves.
                        previous = self.last_aggregate_event.get(index)
                        if previous is not None and now - previous < rule.cooldown:
                            continue
                        self.last_aggregate_event[index] = now
                    events.append({'zoneId': rule.zone_id, 'type': rule.kind,
                                   'trackIds': [o.track_id for o in group], 'count': len(group),
                                   'durationSeconds': now - since,
                                   'confidence': min(o.confidence for o in group)})
        held = {key for key in self.since if key[1] is None and key not in present
                 and now - self.last_inside.get(key, float('-inf')) <= self.count_grace}
        self.since = {key: value for key, value in self.since.items() if key in present or key in held}
        observed_ids = {o.track_id for o in observations}
        retained = {key for key in self.fired if key in present or key in held or (
            key[1] is not None and key[1] not in observed_ids
            and now - self.last_inside.get(key, now) <= self.max_gap)}
        self.fired.intersection_update(retained)
        self.last_inside = {key: value for key, value in self.last_inside.items()
                            if key in present or key in retained or key in held}
        self.anchors = {key: value for key, value in self.anchors.items() if key in present}
        return events
