"use client";

import {
  BarChart,
  Bar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

export type BarSeries = {
  key: string;
  label: string;
  color: string;
  stackId?: string;
};

export type BarDatum = Record<string, number | string>;

const tooltipStyle = {
  backgroundColor: "#0f172a",
  borderRadius: 12,
  border: "none",
  color: "#fff",
  padding: "8px 12px",
  fontSize: 12,
};

export const StackedBarChart = ({
  data,
  series,
  layout = "horizontal",
}: {
  data: BarDatum[];
  series: BarSeries[];
  layout?: "horizontal" | "vertical";
}) => {
  if (!data.length) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        No data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
      <BarChart
        data={data}
        layout={layout}
        margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2a44" />
        {layout === "horizontal" ? (
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#cbd5f5" }} />
        ) : (
          <XAxis type="number" tick={{ fontSize: 11, fill: "#cbd5f5" }} />
        )}
        {layout === "horizontal" ? (
          <YAxis tick={{ fontSize: 11, fill: "#cbd5f5" }} />
        ) : (
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#cbd5f5" }} />
        )}
        <Tooltip contentStyle={tooltipStyle} />
        {series.map((entry) => (
          <Bar
            key={entry.key}
            dataKey={entry.key}
            name={entry.label}
            stackId={entry.stackId}
            fill={entry.color}
            radius={[6, 6, 6, 6]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
};






