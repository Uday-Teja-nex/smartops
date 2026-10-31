import type { IncidentReport } from "./api";

// Quoting alone does not stop spreadsheet formula execution.
const cell = (value: string | number | null) => {
  let text = value === null ? "" : String(value);
  if (/^[\s\u0000-\u001f]*[=+@-]/.test(text)) text = "'" + text;
  return `"${text.replaceAll('"', '""')}"`;
};

export function reportCsv(daily: IncidentReport, weekly: IncidentReport): string {
  const rows: (string | number | null)[][] = [["period", "start_inclusive", "end_exclusive", "timezone", "building_id", "section", "metric", "value", "unit"]];
  for (const [period, report] of [["24h", daily], ["7d", weekly]] as const) {
    const add = (section: string, metric: string, value: number | null, unit = "count") =>
      rows.push([period, report.start, report.end, report.timezone, report.buildingId, section, metric, value, unit]);
    add("summary", "total_incidents", report.totalIncidents);
    add("summary", "average_acknowledgement", report.averageAckMinutes, "minutes; blank means no samples");
    add("summary", "average_resolution", report.averageResolveMinutes, "minutes; blank means no samples");
    add("summary", "acknowledgement_samples", report.acknowledgedCount);
    add("summary", "resolution_samples", report.resolvedTimeCount);
    add("summary", "resolved_or_false_positive_fraction", report.completionRate, "fraction of all incidents");
    add("summary", "false_positive_fraction", report.falsePositiveRate, "fraction of all incidents");
    for (const [section, counts] of [["category", report.categories], ["event_type", report.types], ["current_status", report.statuses]] as const) {
      for (const [label, count] of Object.entries(counts).sort(([a], [b]) => a.localeCompare(b))) add(section, label, count);
    }
    for (const day of report.daily) add("UTC_day_partial_at_boundaries", day.date, day.count);
  }
  return "\uFEFF" + rows.map(row => row.map(cell).join(",")).join("\r\n") + "\r\n";
}

export function downloadReportCsv(daily: IncidentReport, weekly: IncidentReport) {
  const url = URL.createObjectURL(new Blob([reportCsv(daily, weekly)], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `smartops-report-${weekly.end.slice(0, 10)}.csv`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
