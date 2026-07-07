import { EventStatus } from "@/lib/types";
import { hexToRgba, STATUS_COLORS } from "@/lib/visuals";

export const StatusPill = ({ status }: { status: EventStatus }) => (
  <span
    className="inline-flex items-center rounded-full border border-transparent px-3 py-1 text-xs font-semibold capitalize"
    style={{
      backgroundColor: hexToRgba(STATUS_COLORS[status], 0.16),
      color: STATUS_COLORS[status],
    }}
  >
    {status.replace("_", " ")}
  </span>
);





