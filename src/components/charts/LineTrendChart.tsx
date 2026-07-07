"use client";

import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

export type LineDatum = Record<string, number | string>;

const tooltipStyle = {
  backgroundColor: "#0f172a",
  borderRadius: 12,
  border: "none",
  color: "#fff",
  padding: "8px 12px",
  fontSize: 12,
};

export const LineTrendChart = ({
  data,
  lines,
}: {
  data: LineDatum[];
  lines: Array<{ key: string; color: string; label?: string }>;
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
      <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2a44" />
        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#cbd5f5" }} />
        <YAxis tick={{ fontSize: 11, fill: "#cbd5f5" }} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} />
        {lines.map((line) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            stroke={line.color}
            strokeWidth={2}
            dot={false}
            name={line.label}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
};






