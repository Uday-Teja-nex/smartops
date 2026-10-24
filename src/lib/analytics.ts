import { EventCategory, EventRecord, EventSeverity, TimeRange } from "./types";
import { clamp } from "./utils";

const RANGE_MINUTES: Record<TimeRange, number> = {
  "4h": 4 * 60,
  "24h": 24 * 60,
  "7d": 7 * 24 * 60,
  "30d": 30 * 24 * 60,
};

export const TIME_RANGE_LABELS: Record<TimeRange, string> = {
  "4h": "Last 4 hours",
  "24h": "Last 24 hours",
  "7d": "Last 7 days",
  "30d": "Last 30 days",
};

export const filterEventsByRange = (events: EventRecord[], range: TimeRange) => {
  const now = Date.now();
  const maxAge = RANGE_MINUTES[range] * 60 * 1000;
  return events.filter((event) => {
    const startTime = new Date(event.startTime).getTime();
    return now - startTime <= maxAge;
  });
};

export const countBy = <T extends string>(items: T[]) =>
  items.reduce<Record<T, number>>((acc, item) => {
    acc[item] = (acc[item] ?? 0) + 1;
    return acc;
  }, {} as Record<T, number>);

export const getActiveEvents = (events: EventRecord[]) =>
  events.filter((event) => event.status === "active");

export const getCountsByCategory = (events: EventRecord[]) =>
  countBy(events.map((event) => event.category));

export const getCountsBySeverity = (events: EventRecord[]) =>
  countBy(events.map((event) => event.severity));

export const getCountsByStatus = (events: EventRecord[]) =>
  countBy(events.map((event) => event.status));

export const getHotspots = (events: EventRecord[], limit = 6) => {
  const zoneMap = new Map<string, { zone: string; count: number }>();
  events.forEach((event) => {
    const entry = zoneMap.get(event.zone) ?? { zone: event.zone, count: 0 };
    entry.count += 1;
    zoneMap.set(event.zone, entry);
  });
  return Array.from(zoneMap.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
};

export const getSlaMetrics = (events: EventRecord[]) => {
  const ackMinutes: number[] = [];
  const resolveMinutes: number[] = [];

  events.forEach((event) => {
    if (event.ackTime) {
      const ackDiff =
        (new Date(event.ackTime).getTime() -
          new Date(event.startTime).getTime()) /
        60000;
      ackMinutes.push(ackDiff);
    }
    if (event.resolvedTime) {
      const resolveDiff =
        (new Date(event.resolvedTime).getTime() -
          new Date(event.startTime).getTime()) /
        60000;
      resolveMinutes.push(resolveDiff);
    }
  });

  const avgAck =
    ackMinutes.reduce((sum, value) => sum + value, 0) /
    (ackMinutes.length || 1);
  const avgResolve =
    resolveMinutes.reduce((sum, value) => sum + value, 0) /
    (resolveMinutes.length || 1);

  const completed = events.filter((event) =>
    ["resolved", "false_positive"].includes(event.status)
  ).length;
  const completionRate = completed / (events.length || 1);

  return {
    avgAckMinutes: avgAck,
    avgResolveMinutes: avgResolve,
    completionRate,
  };
};

export const getCategoryPerformance = (events: EventRecord[]) => {
  const byCategory = new Map<EventCategory, EventRecord[]>();
  events.forEach((event) => {
    const bucket = byCategory.get(event.category) ?? [];
    bucket.push(event);
    byCategory.set(event.category, bucket);
  });

  return Array.from(byCategory.entries()).map(([category, list]) => {
    const active = list.filter((event) => event.status === "active").length;
    const highSeverity = list.filter(
      (event) => event.severity === "high" || event.severity === "critical"
    ).length;
    return { category, active, highSeverity, total: list.length };
  });
};

export const scoreStatus = (count: number, total: number) => {
  if (!total) return "green";
  const ratio = count / total;
  if (ratio > 0.35) return "red";
  if (ratio > 0.2) return "amber";
  return "green";
};

export const severityTone = (severity: EventSeverity) => {
  if (severity === "critical") return "red";
  if (severity === "high") return "amber";
  if (severity === "medium") return "blue";
  return "green";
};

export const buildTrend = (events: EventRecord[]) => {
  const buckets = new Array(7).fill(0).map((_, index) => ({
    day: `D-${6 - index}`,
    count: 0,
  }));
  const now = Date.now();
  events.forEach((event) => {
    const diffDays = Math.floor(
      (now - new Date(event.startTime).getTime()) / (24 * 60 * 60 * 1000)
    );
    if (diffDays >= 0 && diffDays < 7) {
      buckets[6 - diffDays].count += 1;
    }
  });
  const max = Math.max(...buckets.map((entry) => entry.count), 1);
  return buckets.map((entry) => ({
    ...entry,
    value: clamp(entry.count / max, 0, 1),
  }));
};
