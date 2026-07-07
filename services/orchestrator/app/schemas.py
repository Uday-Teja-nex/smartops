from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CameraContext(BaseModel):
    id: str
    buildingId: str
    floor: str
    zone: str


class FrameEvidence(BaseModel):
    timestampSeconds: float
    imageBase64: str


class DetectionEvidence(BaseModel):
    label: str
    confidence: float
    bbox: dict[str, float] = Field(default_factory=dict)
    timestampSeconds: float | None = None


class DetectionContext(BaseModel):
    status: str = "disabled"  # ran | disabled | unavailable
    summary: dict[str, Any] = Field(default_factory=dict)
    detections: list[DetectionEvidence] = Field(default_factory=list)


class CandidateReviewRequest(BaseModel):
    candidateId: str
    sourceUri: str
    sourceName: str
    observedAt: datetime
    windowStart: float | None = None
    windowEnd: float | None = None
    camera: CameraContext
    frames: list[FrameEvidence] = Field(default_factory=list)
    detectionContext: DetectionContext = Field(default_factory=DetectionContext)


class EvidenceDraft(BaseModel):
    thumbnailUrl: str = "/evidence-placeholder.svg"
    clipUrl: str = "/restricted"
    restricted: bool = True


class IncidentDraft(BaseModel):
    id: str
    category: str
    subcategory: str | None = None
    type: str
    severity: str
    confidence: float = Field(ge=0, le=1)
    status: str = "active"
    buildingId: str
    floor: str
    zone: str
    sourceId: str
    cameraId: str
    candidateId: str | None = None
    startTime: datetime
    endTime: datetime | None = None
    slaDueAt: datetime | None = None
    shortSummary: str
    detailedNarrative: list[str]
    recommendedActions: list[str]
    reviewNotes: list[str] = Field(default_factory=list)
    evidence: EvidenceDraft
    assignedTo: str | None = None
    modelProvider: str
    modelVersion: str
    detectionSummary: dict[str, Any] = Field(default_factory=dict)


class CandidateReviewResponse(BaseModel):
    candidateId: str
    createIncident: bool
    routeTo: str
    incident: IncidentDraft | None = None
    notes: list[str] = Field(default_factory=list)
