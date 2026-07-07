import { classNames } from "@/lib/utils";

export const Skeleton = ({ className }: { className?: string }) => (
  <div
    className={classNames(
      "animate-pulse rounded-xl bg-white/5",
      className ?? "h-4 w-full"
    )}
  />
);

export const SkeletonPanel = ({ lines = 3 }: { lines?: number }) => (
  <div className="glass-panel space-y-3 p-5">
    <Skeleton className="h-3 w-1/3" />
    {Array.from({ length: lines }).map((_, index) => (
      <Skeleton key={index} className="h-4 w-full" />
    ))}
  </div>
);
