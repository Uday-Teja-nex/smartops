export type EventCategory =
  | "Housekeeping"
  | "Safety"
  | "Occupancy"
  | "Security"
  | "Queue & Crowd"
  | "System Health";

export type EventSeverity = "low" | "medium" | "high" | "critical";

export type EventStatus =
  | "active"
  | "acknowledged"
  | "assigned"
  | "in_progress"
  | "resolved"
  | "false_positive"
  | "escalated"
  | "human_review";

export type EventType = string;

export type TimeRange = "4h" | "24h" | "7d" | "30d";
export type SourceType = "file" | "rtsp" | "onvif" | "webrtc";
export type SourceStatus = "online" | "offline" | "paused" | "failing" | "processing";
export type BackendStatus = "connected" | "loading" | "offline";

export type Evidence = {
  thumbnailUrl: string;
  clipUrl: string;
  restricted: boolean;
};

export type DetectionBox = {
  x: number;
  y: number;
  w: number;
  h: number;
};

export type DetectionRecord = {
  id: string;
  sourceId: string;
  candidateId: string;
  label: string;
  confidence: number;
  bbox: DetectionBox;
  frameTs: number;
  frameIndex: number;
  modelName: string;
  createdAt: string;
};

export type EvidenceItem = {
  id: string;
  incidentId: string | null;
  sourceId: string;
  candidateId: string | null;
  kind: "snapshot" | "thumbnail" | "clip" | "metadata";
  contentType: string;
  width: number | null;
  height: number | null;
  durationSeconds: number | null;
  sizeBytes: number | null;
  restricted: boolean;
  meta: Record<string, unknown>;
  createdAt: string;
};

export type IncidentAuditEvent = {
  id: string;
  actor: string;
  action: string;
  fromStatus: string | null;
  toStatus: string | null;
  note: string | null;
  createdAt: string;
};

export type IncidentComment = {
  id: string;
  author: string;
  body: string;
  createdAt: string;
};

export type EventRecord = {
  id: string;
  category: EventCategory;
  subcategory?: string | null;
  type: EventType;
  severity: EventSeverity;
  confidence: number;
  status: EventStatus;
  buildingId: string;
  floor: string;
  zone: string;
  sourceId: string;
  candidateId?: string | null;
  startTime: string;
  endTime: string | null;
  ackTime?: string | null;
  resolvedTime?: string | null;
  slaDueAt?: string | null;
  escalatedAt?: string | null;
  shortSummary: string;
  detailedNarrative: string[];
  recommendedActions: string[];
  reviewNotes?: string[];
  evidence: Evidence;
  assignedTo: string | null;
  modelProvider?: string;
  modelVersion?: string;
  detectionSummary?: Record<string, unknown>;
};

export type IncidentDetail = EventRecord & {
  events: IncidentAuditEvent[];
  comments: IncidentComment[];
  evidenceItems: EvidenceItem[];
  detections: DetectionRecord[];
};

export type ZoneRecord = {
  id: string;
  name: string;
  kind: string;
};

export type FloorRecord = {
  id: string;
  level: string;
  name: string;
  zones: ZoneRecord[];
};

export type Building = {
  id: string;
  name: string;
  address: string;
  timezone?: string;
  floors?: FloorRecord[];
};

export type SourceHealth = {
  lastSeen?: string | null;
  lastError?: string | null;
  latencyMs?: number | null;
  adapter?: string | null;
  reportedStatus?: string | null;
  [key: string]: unknown;
};

export type ZoneRuleConfig = {
  type: string;
  threshold?: number;
  durationSeconds?: number;
  radius?: number;
  movementTolerance?: number;
  timezone?: string;
  allowedHours?: Array<{ days: number[]; start: string; end: string }>;
};
export type DetectionZone = { id: string; polygon: [number, number][]; rules: ZoneRuleConfig[] };

export type DetectionConfig = {
  zones?: DetectionZone[];
  windowSeconds?: number;
  sampleFramesPerWindow?: number;
  minConfidence?: number;
  detectors?: string[];
  [key: string]: unknown;
};

export type LiveObservation = {
  sourceId: string;
  sequence: number;
  capturedAt: string;
  width: number;
  height: number;
  previewJpeg: string | null;
  detections: Array<{ label: string; confidence: number; bbox: { x: number; y: number; w: number; h: number } }>;
  tracks: Array<{ track_id: number; label: string; x: number; y: number; confidence: number }>;
};

export type SourceRecord = {
  id: string;
  orgId: string;
  name: string;
  buildingId: string;
  floorId: string | null;
  zoneId: string | null;
  floor: string;
  zone: string;
  sourceType: SourceType;
  sourceUri: string;
  inputFormat: string | null;
  credentialsRef: string | null;
  enabled: boolean;
  status: SourceStatus;
  health: SourceHealth;
  tags: string[];
  positionNotes: string | null;
  detectionConfig: DetectionConfig;
  createdAt: string;
  updatedAt: string;
};

export type SourceCreateInput = {
  name: string;
  buildingId: string;
  floorId?: string | null;
  zoneId?: string | null;
  floor?: string | null;
  zone?: string | null;
  sourceType: SourceType;
  sourceUri: string;
  inputFormat?: string | null;
  credentialsRef?: string | null;
  enabled?: boolean;
  tags?: string[];
  positionNotes?: string | null;
  detectionConfig?: DetectionConfig;
};

export type SourceUpdateInput = Partial<SourceCreateInput> & {
  status?: SourceStatus;
};


export type UserRole =
  | "admin"
  | "supervisor"
  | "operator"
  | "viewer"
  | "security"
  | "ehs";

export type UserRecord = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  active: boolean;
};

export type LoginResponse = {
  token: string;
  user: UserRecord;
};

export type RuntimeSummary = {
  backendMode: "live" | "mock";
  orchestrator: string;
  modelProvider: string;
  activeSourceCount: number;
  totalSourceCount: number;
};

export type BackendBootstrapResponse = {
  buildings: Building[];
  sources: SourceRecord[];
  incidents: EventRecord[];
  runtime: RuntimeSummary;
};

export type PipelineCandidateStatus = {
  candidateId: string;
  state: string;
  sourceId?: string;
  sourceName?: string;
  updatedAt?: string;
  attempt?: number;
  error?: string;
  incidentId?: string;
  [key: string]: unknown;
};

export type PipelineStatus = {
  queue: string;
  queued: number | null;
  deadLetter: number | null;
  recentStatuses: PipelineCandidateStatus[];
};

export type OccupancySnapshot = {
  floor: string;
  peopleCount: number;
  capacity: number;
};

export type ZoneCongestion = {
  zone: string;
  floor: string;
  congestionIndex: number;
  peopleCount: number;
};

export type CleaningZoneCompletion = {
  floor: string;
  zone: string;
  completed: boolean;
  completedAt: string | null;
};
