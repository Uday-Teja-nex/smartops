"use client";

import { LineChart, Line, ResponsiveContainer } from "recharts";

export const MiniSparkline = ({
  data,
  color = "#10b981",
}: {
  data: number[];
  color?: string;
}) => {
  if (!data.length) {
    return (
      <div className="flex h-full items-center justify-center text-[10px] text-slate-400">
        --
      </div>
    );
  }

  const chartData = data.map((value, index) => ({ name: index, value }));

  return (
    <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
      <LineChart data={chartData}>
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};






