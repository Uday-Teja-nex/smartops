"use client";

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

export type DonutDatum = {
  name: string;
  value: number;
  color?: string;
};

const tooltipStyle = {
  backgroundColor: "#0f172a",
  borderRadius: 12,
  border: "none",
  color: "#fff",
  padding: "8px 12px",
  fontSize: 12,
};

export const DonutChart = ({
  data,
  innerRadius = 50,
  outerRadius = 80,
}: {
  data: DonutDatum[];
  innerRadius?: number;
  outerRadius?: number;
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
      <PieChart>
        <Tooltip contentStyle={tooltipStyle} />
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={innerRadius}
          outerRadius={outerRadius}
          paddingAngle={2}
        >
          {data.map((entry) => (
            <Cell key={entry.name} fill={entry.color ?? "#94a3b8"} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
};






