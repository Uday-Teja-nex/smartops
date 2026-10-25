from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.zone_config import validate_detection_config

SourceType = Literal["file", "rtsp", "onvif", "webrtc"]
SourceStatus = Literal["online", "offline", "paused", "failing", "processing"]
IncidentStatus = Literal[
    "active",
    "acknowledged",
    "assigned",
    "in_progress",
    "resolved",
    "false_positive",
    "escalated",
    "human_review",
]


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------


class ZoneResponse(BaseModel):
    id: str
    name: str
    kind: str


class FloorResponse(BaseModel):
    id: str
    level: str
    name: str
    zones: list[ZoneResponse] = Field(default_factory=list)


class BuildingResponse(BaseModel):
    id: str
    name: str
    address: str
    timezone: str = "UTC"
    floors: list[FloorResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class SourceResponse(BaseModel):
    id: str
    orgId: str
    name: str
    buildingId: str
    floorId: str | None = None
    zoneId: str | None = None
    floor: str
    zone: str
    sourceType: SourceType
    sourceUri: str
    inputFormat: str | None = None
    credentialsRef: str | None = None
    enabled: bool
    status: SourceStatus
    health: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    positionNotes: str | None = None
    detectionConfig: dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime
    updatedAt: datetime


class SourceCreateRequest(BaseModel):
    _validate_zones = field_validator('detectionConfig')(validate_detection_config)
    name: str = Field(min_length=1, max_length=120)
    buildingId: str
    floorId: str | None = None
    zoneId: str | None = None
    floor: str | None = None
    zone: str | None = None
    sourceType: SourceType
    sourceUri: str = Field(min_length=1)
    inputFormat: str | None = None
    credentialsRef: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    positionNotes: str | None = None
    detectionConfig: dict[str, Any] = Field(default_factory=dict)


class SourceUpdateRequest(BaseModel):
    _validate_zones = field_validator('detectionConfig')(validate_detection_config)
    name: str | None = None
    buildingId: str | None = None
    floorId: str | None = None
    zoneId: str | None = None
    floor: str | None = None
    zone: str | None = None
    sourceType: SourceType | None = None
    sourceUri: str | None = None
    inputFormat: str | None = None
    credentialsRef: str | None = None
    enabled: bool | None = None
    status: SourceStatus | None = None
    tags: list[str] | None = None
    positionNotes: str | None = None
    detectionConfig: dict[str, Any] | None = None


class SourceHealthReport(BaseModel):
    status: SourceStatus
    lastError: str | None = None
    latencyMs: float | None = None
    adapter: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Detections
# ---------------------------------------------------------------------------


class DetectionBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(ge=0, le=1)
    h: float = Field(ge=0, le=1)


class DetectionCreate(BaseModel):
    sourceId: str
    candidateId: str
    label: str
    confidence: float = Field(ge=0, le=1)
    bbox: DetectionBox
    frameTs: float
    frameIndex: int
    modelName: str


class DetectionBatchCreateRequest(BaseModel):
    detections: list[DetectionCreate]


class DetectionResponse(BaseModel):
    id: str
    sourceId: str
    candidateId: str
    label: str
    confidence: float
    bbox: DetectionBox
    frameTs: float
    frameIndex: int
    modelName: str
    createdAt: datetime


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceResponse(BaseModel):
    thumbnailUrl: str
    clipUrl: str
    restricted: bool


class EvidenceItemResponse(BaseModel):
    id: str
    incidentId: str | None = None
    sourceId: str
    candidateId: str | None = None
    kind: Literal["snapshot", "thumbnail", "clip", "metadata"]
    contentType: str
    width: int | None = None
    height: int | None = None
    durationSeconds: float | None = None
    sizeBytes: int | None = None
    restricted: bool
    meta: dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime


class EvidenceItemCreateRequest(BaseModel):
    incidentId: str | None = None
    sourceId: str
    candidateId: str | None = None
    kind: Literal["snapshot", "thumbnail", "clip", "metadata"]
    objectKey: str
    contentType: str
    width: int | None = None
    height: int | None = None
    durationSeconds: float | None = None
    sizeBytes: int | None = None
    restricted: bool = True
    meta: dict[str, Any] = Field(default_factory=dict)


class EvidenceUrlResponse(BaseModel):
    id: str
    url: str
    expiresInSeconds: int


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


class IncidentEventResponse(BaseModel):
    id: str
    actor: str
    action: str
    fromStatus: str | None = None
    toStatus: str | None = None
    note: str | None = None
    createdAt: datetime


class IncidentCommentResponse(BaseModel):
    id: str
    author: str
    body: str
    createdAt: datetime


class IncidentCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class EventRecordResponse(BaseModel):
    id: str
    category: str
    subcategory: str | None = None
    type: str
    severity: str
    confidence: float
    status: str
    buildingId: str
    floor: str
    zone: str
    sourceId: str
    candidateId: str | None = None
    startTime: datetime
    endTime: datetime | None = None
    ackTime: datetime | None = None
    resolvedTime: datetime | None = None
    slaDueAt: datetime | None = None
    escalatedAt: datetime | None = None
    shortSummary: str
    detailedNarrative: list[str]
    recommendedActions: list[str]
    reviewNotes: list[str] = Field(default_factory=list)
    evidence: EvidenceResponse
    assignedTo: str | None = None
    modelProvider: str = "unknown"
    modelVersion: str = "unknown"
    detectionSummary: dict[str, Any] = Field(default_factory=dict)


class IncidentDetailResponse(EventRecordResponse):
    events: list[IncidentEventResponse] = Field(default_factory=list)
    comments: list[IncidentCommentResponse] = Field(default_factory=list)
    evidenceItems: list[EvidenceItemResponse] = Field(default_factory=list)
    detections: list[DetectionResponse] = Field(default_factory=list)


class IncidentAssignRequest(BaseModel):
    assignee: str = Field(default="SmartOps Dispatch", min_length=1)


class IncidentStatusUpdateRequest(BaseModel):
    status: IncidentStatus
    note: str | None = None


class IncidentCreateRequest(BaseModel):
    id: str | None = None
    category: str
    subcategory: str | None = None
    type: str
    severity: str
    confidence: float = Field(ge=0, le=1)
    status: IncidentStatus = "active"
    buildingId: str
    floor: str
    zone: str
    sourceId: str
    candidateId: str | None = None
    startTime: datetime
    endTime: datetime | None = None
    slaDueAt: datetime | None = None
    shortSummary: str
    detailedNarrative: list[str] = Field(default_factory=list)
    recommendedActions: list[str] = Field(default_factory=list)
    reviewNotes: list[str] = Field(default_factory=list)
    evidence: EvidenceResponse
    assignedTo: str | None = None
    modelProvider: str = "unknown"
    modelVersion: str = "unknown"
    detectionSummary: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Users / runtime / bootstrap
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    active: bool


class RuntimeSummaryResponse(BaseModel):
    backendMode: Literal["live", "mock"]
    orchestrator: str
    modelProvider: str
    activeSourceCount: int
    totalSourceCount: int


class BootstrapResponse(BaseModel):
    buildings: list[BuildingResponse]
    sources: list[SourceResponse]
    incidents: list[EventRecordResponse]
    runtime: RuntimeSummaryResponse
