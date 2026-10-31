import { describe, expect, it } from "vitest";
import type { IncidentReport } from "./api";
import { reportCsv } from "./report-export";

const report: IncidentReport = {
  start: "2026-11-01T00:00:00Z", end: "2026-11-02T00:00:00Z", timezone: "UTC", buildingId: "building",
  totalIncidents: 201, categories: { '=HYPERLINK("bad")': 1, 'Safety, "Exit"': 200 },
  types: {}, statuses: {}, daily: [{ date: "2026-11-01", count: 201 }],
  acknowledgedCount: 0, resolvedTimeCount: 0, averageAckMinutes: null,
  averageResolveMinutes: null, completionRate: 0, falsePositiveRate: 0,
};

describe("report CSV", () => {
  it("preserves the snapshot and distinguishes missing samples from zero", () => {
    const csv = reportCsv(report, report);
    expect(csv).toContain('"total_incidents","201","count"');
    expect(csv).toContain('"average_acknowledgement","","minutes; blank means no samples"');
    expect(csv).toContain('"false_positive_fraction","0","fraction of all incidents"');
    expect(csv).toContain('"24h","2026-11-01T00:00:00Z","2026-11-02T00:00:00Z"');
    expect(csv).toContain('"7d","2026-11-01T00:00:00Z","2026-11-02T00:00:00Z"');
  });
  it("escapes CSV punctuation and neutralizes spreadsheet formulas", () => {
    const csv = reportCsv(report, report);
    expect(csv).toContain('"\'=HYPERLINK(""bad"")"');
    expect(csv).toContain('"Safety, ""Exit"""');
    expect(csv.startsWith("\uFEFF")).toBe(true);
  });
});
