export const classNames = (...values: Array<string | false | null | undefined>) =>
  values.filter(Boolean).join(" ");

export const formatDateTime = (isoString: string) => {
  const date = new Date(isoString);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }).format(date);
};

export const formatDurationMinutes = (minutes: number) => {
  if (!Number.isFinite(minutes)) return "-";
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const hours = minutes / 60;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  const days = hours / 24;
  return `${days.toFixed(1)}d`;
};

export const formatPercent = (value: number) =>
  `${Math.round(value * 100)}%`;

export const formatConfidence = (value: number) => {
  const normalized = value <= 1 ? value * 100 : value;
  return `${Math.round(normalized)}%`;
};

export const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

export const getNowTimestamp = () => Date.now();






/** "false_positive" -> "False positive"; leaves already-readable labels alone. */
export const humanize = (value: string) => {
  if (!/[_-]/.test(value) && value !== value.toLowerCase()) return value;
  const words = value.replaceAll("_", " ").replaceAll("-", " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};
