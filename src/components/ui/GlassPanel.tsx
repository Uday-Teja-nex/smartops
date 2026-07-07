import { HTMLAttributes } from "react";
import { classNames } from "@/lib/utils";

type GlassPanelProps = HTMLAttributes<HTMLDivElement> & {
  strong?: boolean;
  padded?: boolean;
};

export const GlassPanel = ({
  strong = false,
  padded = true,
  className,
  children,
  ...rest
}: GlassPanelProps) => (
  <div
    className={classNames(
      strong ? "glass-panel-strong" : "glass-panel",
      padded && "p-5",
      className
    )}
    {...rest}
  >
    {children}
  </div>
);
