import { EventRecord } from "@/lib/types";

export type AlertFilters = {
  category: string;
  severity: string;
  status: string;
  floor: string;
  zone: string;
};

const SelectField = ({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) => (
  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
    {label}
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="mt-2 w-full rounded-lg border border-[color:var(--border)] bg-[color:var(--surface-2)] px-3 py-2 text-sm text-slate-200 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
    >
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  </label>
);

export const FiltersBar = ({
  events,
  filters,
  onChange,
}: {
  events: EventRecord[];
  filters: AlertFilters;
  onChange: (next: AlertFilters) => void;
}) => {
  const floors = Array.from(new Set(events.map((event) => event.floor)));
  const zones = Array.from(new Set(events.map((event) => event.zone)));

  return (
    <div className="grid gap-3 rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)]/95 p-4 shadow-[0_22px_70px_-45px_rgba(2,6,23,0.85)] md:grid-cols-5">
      <SelectField
        label="Category"
        value={filters.category}
        options={[
          "All",
          "Safety",
          "Housekeeping",
          "Occupancy",
          "Security",
          "Queue & Crowd",
          "System Health",
        ]}
        onChange={(value) => onChange({ ...filters, category: value })}
      />
      <SelectField
        label="Severity"
        value={filters.severity}
        options={["All", "low", "medium", "high", "critical"]}
        onChange={(value) => onChange({ ...filters, severity: value })}
      />
      <SelectField
        label="Status"
        value={filters.status}
        options={[
          "All",
          "active",
          "acknowledged",
          "assigned",
          "in_progress",
          "resolved",
          "false_positive",
          "escalated",
          "human_review",
        ]}
        onChange={(value) => onChange({ ...filters, status: value })}
      />
      <SelectField
        label="Floor"
        value={filters.floor}
        options={["All", ...floors]}
        onChange={(value) => onChange({ ...filters, floor: value })}
      />
      <SelectField
        label="Zone"
        value={filters.zone}
        options={["All", ...zones]}
        onChange={(value) => onChange({ ...filters, zone: value })}
      />
    </div>
  );
};


