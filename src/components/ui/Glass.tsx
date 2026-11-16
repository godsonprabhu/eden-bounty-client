import { cn } from "@/lib/utils";

type GlassVariant = "default" | "strong" | "inset" | "frame";

const VARIANT: Record<GlassVariant, string> = {
  default: "eb-glass",
  strong: "eb-glass-strong",
  inset: "eb-glass-inset",
  frame: "eb-frame",
};

type GlassProps<T extends React.ElementType> = {
  as?: T;
  variant?: GlassVariant;
  interactive?: boolean;
  className?: string;
} & Omit<React.ComponentPropsWithoutRef<T>, "as" | "className">;

/**
 * Reusable glass surface backed by the shared `--glass-*` tokens in globals.css.
 * Works in both themes and on public, login and admin surfaces.
 */
export function Glass<T extends React.ElementType = "div">({
  as,
  variant = "default",
  interactive = false,
  className,
  ...rest
}: GlassProps<T>) {
  const Component = (as ?? "div") as React.ElementType;
  return <Component className={cn(VARIANT[variant], interactive && "eb-glass-hover", className)} {...rest} />;
}
