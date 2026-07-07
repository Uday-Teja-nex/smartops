"""Event taxonomy for SmartOps incidents.

category/subcategory pairs cover the six product areas. Every entry defines
default severity, SLA, and operator copy used when the model omits them.
"""

from __future__ import annotations

from typing import TypedDict


class CatalogEntry(TypedDict):
    category: str
    subcategory: str
    severity: str
    sla_minutes: int
    summary: str
    actions: list[str]


EVENT_CATALOG: dict[str, CatalogEntry] = {
    # ------------------------------------------------------------------ Safety
    "exit_blocked": {
        "category": "Safety",
        "subcategory": "blocked_exit",
        "severity": "critical",
        "sla_minutes": 15,
        "summary": "Emergency exit path blocked",
        "actions": [
            "Dispatch response team immediately.",
            "Clear the obstruction.",
            "Run follow-up safety check.",
        ],
    },
    "fire_equipment_obstructed": {
        "category": "Safety",
        "subcategory": "fire_equipment_obstructed",
        "severity": "high",
        "sla_minutes": 60,
        "summary": "Fire safety equipment obstructed",
        "actions": [
            "Clear obstruction.",
            "Notify floor warden.",
            "Reconfirm compliance zone.",
        ],
    },
    "slip_trip_hazard": {
        "category": "Safety",
        "subcategory": "slip_trip_hazard",
        "severity": "high",
        "sla_minutes": 60,
        "summary": "Slip or trip hazard",
        "actions": [
            "Place warning signage.",
            "Clean or remove the hazard.",
            "Confirm walkway reopened.",
        ],
    },
    "wet_floor_no_sign": {
        "category": "Safety",
        "subcategory": "wet_floor",
        "severity": "medium",
        "sla_minutes": 240,
        "summary": "Wet floor without signage",
        "actions": [
            "Deploy wet floor sign.",
            "Dry the surface.",
            "Notify housekeeping lead.",
        ],
    },
    "fallen_object": {
        "category": "Safety",
        "subcategory": "fallen_object",
        "severity": "medium",
        "sla_minutes": 240,
        "summary": "Object detected in walkway",
        "actions": [
            "Review sampled frame.",
            "Remove object if confirmed.",
            "Log human verification outcome.",
        ],
    },
    # ------------------------------------------------------------ Housekeeping
    "restroom_service_needed": {
        "category": "Housekeeping",
        "subcategory": "restroom_service",
        "severity": "medium",
        "sla_minutes": 240,
        "summary": "Restroom entry service-needed signal",
        "actions": [
            "Dispatch attendant to entry zone.",
            "Restock consumables.",
            "Verify signage after service.",
        ],
    },
    "bin_overflow": {
        "category": "Housekeeping",
        "subcategory": "bin_overflow",
        "severity": "medium",
        "sla_minutes": 240,
        "summary": "Bin overflow risk",
        "actions": [
            "Prioritize bin swap.",
            "Sweep surrounding area.",
            "Log service completion time.",
        ],
    },
    "litter_hotspot": {
        "category": "Housekeeping",
        "subcategory": "litter_hotspot",
        "severity": "low",
        "sla_minutes": 1440,
        "summary": "Recurring litter hotspot",
        "actions": [
            "Spot clean the area.",
            "Add a nearby bin if recurrence continues.",
            "Monitor during peak traffic.",
        ],
    },
    "cleaning_missed": {
        "category": "Housekeeping",
        "subcategory": "cleaning_missed",
        "severity": "medium",
        "sla_minutes": 480,
        "summary": "Scheduled cleaning appears missed",
        "actions": [
            "Verify cleaning log for the zone.",
            "Dispatch cleaning crew.",
            "Update SLA tracker after completion.",
        ],
    },
    # --------------------------------------------------------------- Occupancy
    "floor_occupancy_spike": {
        "category": "Occupancy",
        "subcategory": "occupancy_spike",
        "severity": "medium",
        "sla_minutes": 240,
        "summary": "Floor occupancy spike",
        "actions": [
            "Alert floor host.",
            "Review meeting schedule.",
            "Monitor congestion index.",
        ],
    },
    "crowding": {
        "category": "Occupancy",
        "subcategory": "crowding",
        "severity": "medium",
        "sla_minutes": 240,
        "summary": "Unusual crowding detected",
        "actions": [
            "Confirm crowd size on evidence frames.",
            "Notify floor operations.",
            "Monitor for dispersal.",
        ],
    },
    # ---------------------------------------------------------------- Security
    "restricted_zone_entry": {
        "category": "Security",
        "subcategory": "restricted_zone_entry",
        "severity": "high",
        "sla_minutes": 30,
        "summary": "Possible entry into restricted zone",
        "actions": [
            "Verify authorization on evidence frames.",
            "Notify security desk.",
            "Log outcome for audit.",
        ],
    },
    "tailgating_candidate": {
        "category": "Security",
        "subcategory": "tailgating",
        "severity": "medium",
        "sla_minutes": 60,
        "summary": "Possible tailgating at controlled door",
        "actions": [
            "Review entry footage.",
            "Cross-check badge events.",
            "Escalate to security if confirmed.",
        ],
    },
    # ----------------------------------------------------------- Queue & Crowd
    "queue_buildup": {
        "category": "Queue & Crowd",
        "subcategory": "queue_buildup",
        "severity": "medium",
        "sla_minutes": 60,
        "summary": "Queue building beyond comfort threshold",
        "actions": [
            "Open an additional service lane.",
            "Notify the area host.",
            "Recheck queue length in 15 minutes.",
        ],
    },
    "lobby_congestion": {
        "category": "Queue & Crowd",
        "subcategory": "lobby_congestion",
        "severity": "medium",
        "sla_minutes": 60,
        "summary": "Lobby congestion rising",
        "actions": [
            "Open alternate entry lane.",
            "Notify lobby host.",
            "Monitor density trend.",
        ],
    },
    "elevator_queue": {
        "category": "Queue & Crowd",
        "subcategory": "elevator_queue",
        "severity": "low",
        "sla_minutes": 240,
        "summary": "Elevator lobby queue",
        "actions": [
            "Stage additional elevators if available.",
            "Redirect occupants if needed.",
            "Recheck in 15 minutes.",
        ],
    },
    # ----------------------------------------------------------- System Health
    "camera_offline": {
        "category": "System Health",
        "subcategory": "camera_offline",
        "severity": "high",
        "sla_minutes": 120,
        "summary": "Video source offline",
        "actions": [
            "Check source power and network.",
            "Verify adapter health output.",
            "Escalate to facilities IT if unresolved.",
        ],
    },
    "feed_degraded": {
        "category": "System Health",
        "subcategory": "feed_degraded",
        "severity": "medium",
        "sla_minutes": 240,
        "summary": "Video feed degraded",
        "actions": [
            "Compare recent frames against baseline quality.",
            "Check bandwidth and encoder settings.",
            "Schedule maintenance if persistent.",
        ],
    },
}

VLM_REVIEWABLE_TYPES = [
    event_type
    for event_type, entry in EVENT_CATALOG.items()
    # System Health incidents come from rule-based source monitoring, never
    # from VLM scene review.
    if entry["category"] != "System Health"
]
