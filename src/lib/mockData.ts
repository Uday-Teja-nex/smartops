import {
  Building,
  CleaningZoneCompletion,
  EventCategory,
  EventRecord,
  EventSeverity,
  EventStatus,
  EventType,
  OccupancySnapshot,
  ZoneCongestion,
} from "./types";
import { clamp } from "./utils";

const PRESENTATION_CLOCK_ISO = "2026-06-02T18:30:00.000Z";
const MINUTE = 60 * 1000;
const DAY_MINUTES = 24 * 60;

const addMinutes = (date: Date, minutes: number) =>
  new Date(date.getTime() + minutes * MINUTE);

const seededRandom = (seed: number) => {
  let value = seed;
  return () => {
    value = (value * 9301 + 49297) % 233280;
    return value / 233280;
  };
};

const createMockGenerator = () => {
  const rand = seededRandom(42);

  const randomBetween = (min: number, max: number) =>
    min + rand() * (max - min);

  const pick = <T,>(items: T[]) => items[Math.floor(rand() * items.length)];

  const pickWeighted = <T,>(items: Array<{ item: T; weight: number }>) => {
    const total = items.reduce((sum, entry) => sum + entry.weight, 0);
    const threshold = rand() * total;
    let acc = 0;
    for (const entry of items) {
      acc += entry.weight;
      if (acc >= threshold) return entry.item;
    }
    return items[items.length - 1].item;
  };

  return { pick, pickWeighted, rand, randomBetween };
};

export const BUILDINGS: Building[] = [
  {
    id: "bldg-north-01",
    name: "Northpoint Tower",
    address: "200 Market Plaza",
  },
  {
    id: "bldg-south-02",
    name: "Harbor View",
    address: "88 Bay Street",
  },
];

const ZONES = [
  { floor: "L1", zone: "Lobby Atrium", tag: "lobby" },
  { floor: "L1", zone: "Elevator Bank", tag: "elevator" },
  { floor: "L1", zone: "East Corridor", tag: "corridor" },
  { floor: "L2", zone: "Pantry & Cafe", tag: "pantry" },
  { floor: "L2", zone: "Open Workspace", tag: "workspace" },
  { floor: "L2", zone: "Restroom Entry", tag: "restroom" },
  { floor: "L3", zone: "North Corridor", tag: "corridor" },
  { floor: "L3", zone: "Restroom Entry", tag: "restroom" },
  { floor: "L3", zone: "Server Room Entry", tag: "restricted" },
  { floor: "L4", zone: "Conference Hub", tag: "conference" },
  { floor: "L4", zone: "Elevator Lobby", tag: "elevator" },
  { floor: "L5", zone: "Terrace Entry", tag: "egress" },
  { floor: "L5", zone: "Storage", tag: "storage" },
];

const HOTSPOT_ZONES = [
  "L2 Pantry & Cafe",
  "L3 Restroom Entry",
  "L1 Elevator Bank",
  "L4 Elevator Lobby",
];

const EVENT_LIBRARY: Record<
  EventType,
  {
    category: EventCategory;
    severity: EventSeverity;
    shortSummary: string;
    narrative: string[];
    actions: string[];
  }
> = {
  cleaning_completed: {
    category: "Housekeeping",
    severity: "low",
    shortSummary: "Cleaning pass completed",
    narrative: [
      "Surface wipe down confirmed in shared areas",
      "No privacy-sensitive zones were captured",
      "Cycle logged to housekeeping ledger",
    ],
    actions: [
      "Update completion in logbook",
      "Schedule next round per SLA",
      "Monitor for rework signals",
    ],
  },
  restroom_service_needed: {
    category: "Housekeeping",
    severity: "medium",
    shortSummary: "Restroom entry service-needed signal",
    narrative: [
      "Queue detected near entry and handwash area",
      "Supply indicators show low consumables",
      "No interior restroom footage used",
    ],
    actions: [
      "Dispatch attendant to entry zone",
      "Restock soap and paper",
      "Verify door signage is visible",
    ],
  },
  bin_overflow: {
    category: "Housekeeping",
    severity: "medium",
    shortSummary: "Bin overflow risk",
    narrative: [
      "Waste container nearing capacity",
      "Litter observed within 2 meters",
      "Adjacent traffic volume is high",
    ],
    actions: [
      "Prioritize bin swap",
      "Sweep surrounding area",
      "Log service time for SLA",
    ],
  },
  litter_hotspot: {
    category: "Housekeeping",
    severity: "low",
    shortSummary: "Recurring litter hotspot",
    narrative: [
      "Loose debris detected in shared area",
      "Pattern repeats during peak traffic",
      "No personal identifiers captured",
    ],
    actions: [
      "Spot clean the area",
      "Add additional bin nearby",
      "Monitor during next peak window",
    ],
  },
  missed_clean: {
    category: "Housekeeping",
    severity: "high",
    shortSummary: "Missed clean on scheduled route",
    narrative: [
      "Scheduled cleaning window elapsed",
      "No confirmed completion signal",
      "Escalation required for SLA risk",
    ],
    actions: [
      "Assign immediate re-service",
      "Capture reason code",
      "Update SLA dashboard",
    ],
  },
  rework_required: {
    category: "Housekeeping",
    severity: "medium",
    shortSummary: "Rework required",
    narrative: [
      "Follow-up cleaning requested",
      "Residual debris detected in common area",
      "No restricted zones recorded",
    ],
    actions: [
      "Schedule rework within 2 hours",
      "Confirm completion scan",
      "Document findings",
    ],
  },
  fire_equipment_obstructed: {
    category: "Safety",
    severity: "high",
    shortSummary: "Fire safety equipment obstructed",
    narrative: [
      "Extinguisher or AED access blocked",
      "Obstruction within safety clearance zone",
      "Immediate clearance recommended",
    ],
    actions: [
      "Clear obstruction",
      "Notify floor warden",
      "Reconfirm compliance",
    ],
  },
  exit_blocked: {
    category: "Safety",
    severity: "critical",
    shortSummary: "Emergency exit path blocked",
    narrative: [
      "Egress route partially blocked",
      "Item detected within 1 meter of exit",
      "Safety policy breach logged",
    ],
    actions: [
      "Dispatch response team",
      "Remove obstruction",
      "Run follow-up safety check",
    ],
  },
  slip_trip_hazard: {
    category: "Safety",
    severity: "high",
    shortSummary: "Slip or trip hazard",
    narrative: [
      "Spill or debris detected on walkway",
      "No wet floor signage present",
      "Risk elevated during peak traffic",
    ],
    actions: [
      "Place warning signage",
      "Clean spill area",
      "Confirm area reopened",
    ],
  },
  wet_floor_no_sign: {
    category: "Safety",
    severity: "medium",
    shortSummary: "Wet floor without signage",
    narrative: [
      "Moisture detected on tile surface",
      "Warning sign not visible",
      "Potential slip hazard in shared area",
    ],
    actions: [
      "Deploy wet floor sign",
      "Dry the surface",
      "Notify housekeeping lead",
    ],
  },
  fallen_object: {
    category: "Safety",
    severity: "medium",
    shortSummary: "Fallen object in walkway",
    narrative: [
      "Object detected on floor",
      "Traffic diverted around obstruction",
      "No personal tracking used",
    ],
    actions: [
      "Remove object",
      "Check nearby shelving",
      "Log hazard resolution",
    ],
  },
  lobby_congestion: {
    category: "Occupancy",
    severity: "medium",
    shortSummary: "Lobby congestion rising",
    narrative: [
      "People density exceeds comfort threshold",
      "Queue forms at security checkpoint",
      "Crowding index elevated",
    ],
    actions: [
      "Open alternate entry lane",
      "Notify lobby host",
      "Monitor density trend",
    ],
  },
  elevator_queue: {
    category: "Occupancy",
    severity: "low",
    shortSummary: "Elevator lobby queue",
    narrative: [
      "Queue length exceeds 6 people",
      "Waiting time trending upward",
      "No identity data used",
    ],
    actions: [
      "Stage additional elevators",
      "Redirect to stairs if available",
      "Recheck in 15 minutes",
    ],
  },
  floor_occupancy_spike: {
    category: "Occupancy",
    severity: "medium",
    shortSummary: "Floor occupancy spike",
    narrative: [
      "People count exceeded expected range",
      "Density elevated in common area",
      "Privacy-safe aggregate only",
    ],
    actions: [
      "Alert floor host",
      "Review meeting schedules",
      "Monitor congestion index",
    ],
  },
};

const cameraForZone = (zone: string) => {
  const code = zone
    .replace(/[^A-Za-z0-9]/g, "")
    .slice(0, 4)
    .toUpperCase();
  return `CAM-${code}`;
};

const buildEventRecord = (input: {
  id: string;
  type: EventType;
  severity?: EventSeverity;
  status: EventStatus;
  buildingId: string;
  zone: string;
  floor: string;
  startTime: Date;
  endTime: Date | null;
  confidence: number;
  assignedTo: string | null;
  ackTime?: Date | null;
  resolvedTime?: Date | null;
}) => {
  const template = EVENT_LIBRARY[input.type];
  return {
    id: input.id,
    category: template.category,
    type: input.type,
    severity: input.severity ?? template.severity,
    confidence: input.confidence,
    status: input.status,
    buildingId: input.buildingId,
    floor: input.floor,
    zone: input.zone,
    sourceId: cameraForZone(input.zone),
    cameraId: cameraForZone(input.zone),
    startTime: input.startTime.toISOString(),
    endTime: input.endTime ? input.endTime.toISOString() : null,
    ackTime: input.ackTime ? input.ackTime.toISOString() : null,
    resolvedTime: input.resolvedTime ? input.resolvedTime.toISOString() : null,
    shortSummary: template.shortSummary,
    detailedNarrative: template.narrative,
    recommendedActions: template.actions,
    evidence: {
      thumbnailUrl: "/evidence-placeholder.svg",
      clipUrl: "/restricted",
      restricted: true,
    },
    assignedTo: input.assignedTo,
  } satisfies EventRecord;
};

const chooseZoneForType = (
  type: EventType,
  pick: <T>(items: T[]) => T
) => {
  const tag = (() => {
    if (type === "restroom_service_needed") return "restroom";
    if (type === "bin_overflow" || type === "litter_hotspot") return "pantry";
    if (type === "exit_blocked") return "egress";
    if (type === "fire_equipment_obstructed") return "corridor";
    if (type === "lobby_congestion") return "lobby";
    if (type === "elevator_queue") return "elevator";
    if (type === "floor_occupancy_spike") return "workspace";
    if (type === "wet_floor_no_sign" || type === "slip_trip_hazard")
      return "corridor";
    return "corridor";
  })();

  const matching = ZONES.filter((zone) => zone.tag === tag);
  if (matching.length > 0) return pick(matching);
  return pick(ZONES);
};

const createPatternEvents = (
  buildingId: string,
  now: Date,
  randomBetween: (min: number, max: number) => number
) => {
  const events: EventRecord[] = [];
  for (let dayOffset = 1; dayOffset <= 6; dayOffset += 1) {
    const startBase = addMinutes(now, -(dayOffset * DAY_MINUTES + 360));
    const zone = ZONES.find((entry) => entry.zone === "Pantry & Cafe");
    if (!zone) continue;
    const startTime = addMinutes(startBase, randomBetween(-15, 25));
    const endTime = addMinutes(startTime, randomBetween(20, 60));
    events.push(
      buildEventRecord({
        id: `EVT-PAT-${dayOffset}`,
        type: "exit_blocked",
        severity: "high",
        status: "resolved",
        buildingId,
        zone: `${zone.floor} ${zone.zone}`,
        floor: zone.floor,
        startTime,
        endTime,
        ackTime: addMinutes(startTime, 8),
        resolvedTime: endTime,
        confidence: clamp(randomBetween(86, 96), 0, 100),
        assignedTo: "Facilities Team",
      })
    );
  }
  return events;
};

export const generateEvents = () => {
  const now = new Date(PRESENTATION_CLOCK_ISO);
  const { pick, pickWeighted, rand, randomBetween } = createMockGenerator();
  const totalEvents = 96;
  const activeTarget = 12;
  const events: EventRecord[] = [];
  const buildingId = BUILDINGS[0].id;

  events.push(...createPatternEvents(buildingId, now, randomBetween));

  const eventTypes: EventType[] = Object.keys(EVENT_LIBRARY) as EventType[];

  for (let i = 0; events.length < totalEvents; i += 1) {
    const isActive = events.length < activeTarget;
    const type = pickWeighted(
      eventTypes.map((eventType) => ({
        item: eventType,
        weight: eventType.includes("clean") ? 1.2 : 1,
      }))
    );
    const zoneChoice = pickWeighted(
      ZONES.map((zone) => ({
        item: zone,
        weight: HOTSPOT_ZONES.includes(`${zone.floor} ${zone.zone}`) ? 3 : 1,
      }))
    );
    const zone = rand() > 0.55 ? zoneChoice : chooseZoneForType(type, pick);
    const startOffset = isActive
      ? -randomBetween(5, 140)
      : -randomBetween(60, 7 * DAY_MINUTES);
    const startTime = addMinutes(now, startOffset);
    const status = isActive
      ? "active"
      : pick<EventStatus>([
          "resolved",
          "resolved",
          "assigned",
          "acknowledged",
          "false_positive",
        ]);
    const ackTime =
      status === "acknowledged" ||
      status === "assigned" ||
      status === "resolved" ||
      status === "false_positive"
        ? addMinutes(startTime, randomBetween(5, 40))
        : null;
    const resolvedTime =
      status === "resolved" || status === "false_positive"
        ? addMinutes(startTime, randomBetween(20, 180))
        : null;
    const endTime = resolvedTime ?? null;

    events.push(
      buildEventRecord({
        id: `EVT-${events.length + 1}`,
        type,
        status,
        buildingId,
        zone: `${zone.floor} ${zone.zone}`,
        floor: zone.floor,
        startTime,
        endTime,
        ackTime,
        resolvedTime,
        confidence: clamp(randomBetween(76, 98), 0, 100),
        assignedTo: status === "assigned" || status === "resolved"
          ? pick(["Facilities Team", "Housekeeping Lead", "EHS On-Call"])
          : null,
      })
    );
  }

  return events;
};

export const OCCUPANCY_NOW: OccupancySnapshot[] = [
  { floor: "L1", peopleCount: 162, capacity: 220 },
  { floor: "L2", peopleCount: 214, capacity: 280 },
  { floor: "L3", peopleCount: 176, capacity: 240 },
  { floor: "L4", peopleCount: 98, capacity: 180 },
  { floor: "L5", peopleCount: 64, capacity: 120 },
];

export const ZONE_CONGESTION: ZoneCongestion[] = [
  { floor: "L1", zone: "Lobby Atrium", congestionIndex: 78, peopleCount: 92 },
  { floor: "L1", zone: "Elevator Bank", congestionIndex: 71, peopleCount: 58 },
  { floor: "L2", zone: "Pantry & Cafe", congestionIndex: 69, peopleCount: 46 },
  { floor: "L3", zone: "Restroom Entry", congestionIndex: 56, peopleCount: 28 },
  { floor: "L4", zone: "Elevator Lobby", congestionIndex: 62, peopleCount: 36 },
  { floor: "L5", zone: "Terrace Entry", congestionIndex: 41, peopleCount: 14 },
];

export const CLEANING_COMPLETION: CleaningZoneCompletion[] = [
  { floor: "L1", zone: "Lobby Atrium", completed: true, completedAt: addMinutes(new Date(PRESENTATION_CLOCK_ISO), -90).toISOString() },
  { floor: "L1", zone: "East Corridor", completed: true, completedAt: addMinutes(new Date(PRESENTATION_CLOCK_ISO), -160).toISOString() },
  { floor: "L2", zone: "Pantry & Cafe", completed: false, completedAt: null },
  { floor: "L2", zone: "Restroom Entry", completed: true, completedAt: addMinutes(new Date(PRESENTATION_CLOCK_ISO), -110).toISOString() },
  { floor: "L3", zone: "North Corridor", completed: true, completedAt: addMinutes(new Date(PRESENTATION_CLOCK_ISO), -140).toISOString() },
  { floor: "L3", zone: "Restroom Entry", completed: false, completedAt: null },
  { floor: "L4", zone: "Conference Hub", completed: true, completedAt: addMinutes(new Date(PRESENTATION_CLOCK_ISO), -80).toISOString() },
  { floor: "L4", zone: "Elevator Lobby", completed: true, completedAt: addMinutes(new Date(PRESENTATION_CLOCK_ISO), -70).toISOString() },
  { floor: "L5", zone: "Terrace Entry", completed: true, completedAt: addMinutes(new Date(PRESENTATION_CLOCK_ISO), -120).toISOString() },
  { floor: "L5", zone: "Storage", completed: true, completedAt: addMinutes(new Date(PRESENTATION_CLOCK_ISO), -150).toISOString() },
];





