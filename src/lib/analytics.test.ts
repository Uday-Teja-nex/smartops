import { describe, expect, it } from "vitest";
import {
  countBy,
  filterEventsByRange,
  getActiveEvents,
  getCountsByCategory,
  getHotspots,
  getSlaMetrics,
} from "./analytics";
import { EventRecord } from "./types";

const makeEvent = (overrides: Partial<EventRecord> = {}): EventRecord => ({
  id: `evt-${Math.random().toString(36).slice(2, 8)}`,
  category: "Safety",
  type: "exit_blocked",
  severity: "critical",
  confidence: 0.9,
  status: "active",
  buildingId: "bldg-1",
  floor: "L1",
  zone: "Lobby",
  sourceId: "src-1",
  startTime: new Date().toISOString(),
  endTime: null,
  shortSummary: "test",
  detailedNarrative: [],
  recommendedActions: [],
  evidence: { thumbnailUrl: "/t", clipUrl: "/c", restricted: true },
  assignedTo: null,
  ...overrides,
});

describe("filterEventsByRange", () => {
  it("keeps recent events and drops old ones", () => {
    const recent = makeEvent();
    const old = makeEvent({
      startTime: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    });
    const result = filterEventsByRange([recent, old], "7d");
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(recent.id);
  });

  it("30d keeps what 4h drops", () => {
    const yesterday = makeEvent({
      startTime: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    });
    expect(filterEventsByRange([yesterday], "4h")).toHaveLength(0);
    expect(filterEventsByRange([yesterday], "30d")).toHaveLength(1);
  });
});

describe("aggregations", () => {
  it("countBy counts occurrences", () => {
    expect(countBy(["a", "b", "a"])).toEqual({ a: 2, b: 1 });
  });

  it("getCountsByCategory handles the six-category taxonomy", () => {
    const events = [
      makeEvent({ category: "Safety" }),
      makeEvent({ category: "Security" }),
      makeEvent({ category: "Queue & Crowd" }),
      makeEvent({ category: "Queue & Crowd" }),
      makeEvent({ category: "System Health" }),
    ];
    const counts = getCountsByCategory(events);
    expect(counts["Queue & Crowd"]).toBe(2);
    expect(counts["System Health"]).toBe(1);
  });

  it("getActiveEvents only returns active status", () => {
    const events = [
      makeEvent({ status: "active" }),
      makeEvent({ status: "resolved" }),
      makeEvent({ status: "human_review" }),
    ];
    expect(getActiveEvents(events)).toHaveLength(1);
  });

  it("getHotspots ranks zones by event count", () => {
    const events = [
      makeEvent({ zone: "Lobby" }),
      makeEvent({ zone: "Lobby" }),
      makeEvent({ zone: "Terrace" }),
    ];
    const hotspots = getHotspots(events);
    expect(hotspots[0]).toEqual({ zone: "Lobby", count: 2 });
  });
});

describe("getSlaMetrics", () => {
  it("computes ack and resolve minutes", () => {
    const start = new Date("2026-07-07T10:00:00Z");
    const event = makeEvent({
      startTime: start.toISOString(),
      ackTime: new Date(start.getTime() + 5 * 60000).toISOString(),
      resolvedTime: new Date(start.getTime() + 30 * 60000).toISOString(),
    });
    const metrics = getSlaMetrics([event]);
    expect(Math.round(metrics.avgAckMinutes)).toBe(5);
    expect(Math.round(metrics.avgResolveMinutes)).toBe(30);
  });
});
