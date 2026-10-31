import type { IncidentReport } from "./api";

const escape = (value: string | number) => String(value).replace(/[&<>"']/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[character]!);
const number = (value: number | null, suffix = "") => value === null ? "No data" : `${value.toFixed(1)}${suffix}`;
const table = (heading: string, rows: [string, string | number][]) => `<h2>${escape(heading)}</h2><table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>${rows.map(([label, value]) => `<tr><td>${escape(label)}</td><td>${escape(value)}</td></tr>`).join("")}</tbody></table>`;

export function reportPrintHtml(daily: IncidentReport, weekly: IncidentReport): string {
  const sections = ([["Last 24 hours", daily], ["Last 7 days", weekly]] as const).map(([label, report]) => `
    <section><h1>${escape(label)}</h1>
    <p class="interval">${escape(report.start)} (inclusive) to ${escape(report.end)} (exclusive)</p>
    ${table("Computed summary", [
      ["Total incidents", report.totalIncidents],
      ["Average acknowledgement", number(report.averageAckMinutes, " minutes")],
      ["Acknowledgement samples", report.acknowledgedCount],
      ["Average resolution", number(report.averageResolveMinutes, " minutes")],
      ["Resolution samples", report.resolvedTimeCount],
      ["Resolved or false positive / all incidents", number(report.completionRate === null ? null : report.completionRate * 100, "%")],
      ["Marked false positive / all incidents", number(report.falsePositiveRate === null ? null : report.falsePositiveRate * 100, "%")],
    ])}
    ${table("Categories", Object.entries(report.categories))}
    ${table("Event types", Object.entries(report.types))}
    ${table("Current statuses", Object.entries(report.statuses))}
    ${table("Daily totals (UTC; boundary days may be partial)", report.daily.map(day => [day.date, day.count]))}
    </section>`).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>SmartOps operations report</title>
    <style>@page{size:A4;margin:18mm}body{font:11pt Arial,sans-serif;color:#172033;margin:0}h1{font-size:20pt}h2{font-size:13pt;margin-top:20px;break-after:avoid}p{line-height:1.5}.interval{font-size:9pt;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;margin-bottom:14px;table-layout:fixed}th,td{padding:7px;border-bottom:1px solid #ccd3dd;text-align:left;overflow-wrap:anywhere}th{background:#edf1f6}thead{display:table-header-group}tr{break-inside:avoid}section+section{break-before:page}.note{font-size:9pt;color:#455269}</style></head>
    <body><header><h1>SmartOps operations report</h1><p>Building: ${escape(weekly.buildingId ?? "All workspace buildings")}</p>
    <p class="note">Computed from stored incident records. No AI-generated narrative. This is the displayed snapshot, not a live report. Timing averages include recorded non-negative durations only; No data means no samples. Statuses reflect the stored state when queried.</p></header>${sections}</body></html>`;
}

export function printReport(daily: IncidentReport, weekly: IncidentReport) {
  const frame = document.createElement("iframe");
  frame.title = "Printable operations report";
  frame.style.cssText = "position:fixed;width:0;height:0;border:0;left:-10000px";
  frame.onload = () => {
    const target = frame.contentWindow;
    if (!target) { frame.remove(); return; }
    target.onafterprint = () => frame.remove();
    target.focus();
    target.print();
  };
  frame.srcdoc = reportPrintHtml(daily, weekly);
  document.body.appendChild(frame);
}
