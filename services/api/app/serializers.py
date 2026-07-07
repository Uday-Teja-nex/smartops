from app.models import (
    BuildingModel,
    DetectionModel,
    EvidenceItemModel,
    IncidentCommentModel,
    IncidentEventModel,
    IncidentModel,
    SourceModel,
    UserModel,
)
from app.schemas import (
    BuildingResponse,
    CameraResponse,
    DetectionBox,
    DetectionResponse,
    EventRecordResponse,
    EvidenceItemResponse,
    EvidenceResponse,
    FloorResponse,
    IncidentCommentResponse,
    IncidentDetailResponse,
    IncidentEventResponse,
    SourceResponse,
    UserResponse,
    ZoneResponse,
)


def serialize_building(model: BuildingModel) -> BuildingResponse:
    return BuildingResponse(
        id=model.id,
        name=model.name,
        address=model.address,
        timezone=model.timezone,
        floors=[
            FloorResponse(
                id=floor.id,
                level=floor.level,
                name=floor.name,
                zones=[
                    ZoneResponse(id=zone.id, name=zone.name, kind=zone.kind)
                    for zone in floor.zones
                ],
            )
            for floor in model.floors
        ],
    )


def serialize_source(model: SourceModel) -> SourceResponse:
    return SourceResponse(
        id=model.id,
        orgId=model.org_id,
        name=model.name,
        buildingId=model.building_id,
        floorId=model.floor_id,
        zoneId=model.zone_id,
        floor=model.floor_label,
        zone=model.zone_label,
        sourceType=model.source_type,
        sourceUri=model.source_uri,
        inputFormat=model.input_format,
        credentialsRef=model.credentials_ref,
        enabled=model.enabled,
        status=model.status,
        health=model.health or {},
        tags=model.tags or [],
        positionNotes=model.position_notes,
        detectionConfig=model.detection_config or {},
        createdAt=model.created_at,
        updatedAt=model.updated_at,
    )


def serialize_source_as_camera(model: SourceModel) -> CameraResponse:
    return CameraResponse(
        id=model.id,
        name=model.name,
        buildingId=model.building_id,
        floor=model.floor_label,
        zone=model.zone_label,
        sourceType=model.source_type,
        sourceUri=model.source_uri,
        enabled=model.enabled,
        status=model.status,
    )


def serialize_detection(model: DetectionModel) -> DetectionResponse:
    return DetectionResponse(
        id=model.id,
        sourceId=model.source_id,
        candidateId=model.candidate_id,
        label=model.label,
        confidence=model.confidence,
        bbox=DetectionBox(x=model.bbox_x, y=model.bbox_y, w=model.bbox_w, h=model.bbox_h),
        frameTs=model.frame_ts,
        frameIndex=model.frame_index,
        modelName=model.model_name,
        createdAt=model.created_at,
    )


def serialize_evidence_item(model: EvidenceItemModel) -> EvidenceItemResponse:
    return EvidenceItemResponse(
        id=model.id,
        incidentId=model.incident_id,
        sourceId=model.source_id,
        candidateId=model.candidate_id,
        kind=model.kind,
        contentType=model.content_type,
        width=model.width,
        height=model.height,
        durationSeconds=model.duration_seconds,
        sizeBytes=model.size_bytes,
        restricted=model.restricted,
        meta=model.meta or {},
        createdAt=model.created_at,
    )


def serialize_incident_event(model: IncidentEventModel) -> IncidentEventResponse:
    return IncidentEventResponse(
        id=model.id,
        actor=model.actor,
        action=model.action,
        fromStatus=model.from_status,
        toStatus=model.to_status,
        note=model.note,
        createdAt=model.created_at,
    )


def serialize_incident_comment(model: IncidentCommentModel) -> IncidentCommentResponse:
    return IncidentCommentResponse(
        id=model.id,
        author=model.author,
        body=model.body,
        createdAt=model.created_at,
    )


def _incident_fields(model: IncidentModel) -> dict:
    return {
        "id": model.id,
        "category": model.category,
        "subcategory": model.subcategory,
        "type": model.event_type,
        "severity": model.severity,
        "confidence": model.confidence,
        "status": model.status,
        "buildingId": model.building_id,
        "floor": model.floor,
        "zone": model.zone,
        "sourceId": model.source_id,
        "cameraId": model.source_id,
        "candidateId": model.candidate_id,
        "startTime": model.start_time,
        "endTime": model.end_time,
        "ackTime": model.ack_time,
        "resolvedTime": model.resolved_time,
        "slaDueAt": model.sla_due_at,
        "escalatedAt": model.escalated_at,
        "shortSummary": model.short_summary,
        "detailedNarrative": model.detailed_narrative,
        "recommendedActions": model.recommended_actions,
        "reviewNotes": model.review_notes or [],
        "evidence": EvidenceResponse(
            thumbnailUrl=model.evidence_thumbnail_url,
            clipUrl=model.evidence_clip_url,
            restricted=model.evidence_restricted,
        ),
        "assignedTo": model.assigned_to,
        "modelProvider": model.model_provider,
        "modelVersion": model.model_version,
        "detectionSummary": model.detection_summary or {},
    }


def serialize_incident(model: IncidentModel) -> EventRecordResponse:
    return EventRecordResponse(**_incident_fields(model))


def serialize_incident_detail(
    model: IncidentModel,
    detections: list[DetectionModel] | None = None,
    evidence_items: list[EvidenceItemModel] | None = None,
) -> IncidentDetailResponse:
    items = evidence_items if evidence_items is not None else model.evidence_items
    return IncidentDetailResponse(
        **_incident_fields(model),
        events=[serialize_incident_event(event) for event in model.events],
        comments=[serialize_incident_comment(comment) for comment in model.comments],
        evidenceItems=[serialize_evidence_item(item) for item in items],
        detections=[serialize_detection(det) for det in (detections or [])],
    )


def serialize_user(model: UserModel) -> UserResponse:
    return UserResponse(
        id=model.id,
        email=model.email,
        name=model.name,
        role=model.role,
        active=model.active,
    )
