"use client";

import { hexToRgba } from "@/lib/visuals";

export type HeatmapItem = {
  label: string;
  value: number;
};

export const HeatmapGrid = ({
  items,
  accent = "#6366f1",
  columns = 4,
  max,
}: {
  items: HeatmapItem[];
  accent?: string;
  columns?: number;
  max?: number;
}) => {
  if (!items.length) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        No hotspot data
      </div>
    );
  }

  const maxValue = max ?? Math.max(...items.map((item) => item.value), 1);

  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
      {items.map((item) => {
        const intensity = Math.min(item.value / maxValue, 1);
        return (
          <div
            key={item.label}
            className="rounded-xl border border-[color:var(--border)] px-3 py-3 text-xs text-slate-200"
            style={{
              backgroundColor: hexToRgba(accent, 0.1 + intensity * 0.35),
            }}
            aria-label={`${item.label}: ${item.value} events`}
          >
            <p className="font-semibold text-slate-100">{item.label}</p>
            <p className="text-[11px] text-slate-400">{item.value} signals</p>
          </div>
        );
      })}
    </div>
  );
};





