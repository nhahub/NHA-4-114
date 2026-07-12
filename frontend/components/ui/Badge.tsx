import clsx from "clsx";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "accent" | "muted";
  className?: string;
}

export default function Badge({
  children,
  variant = "default",
  className,
}: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-mono border",
        {
          "bg-surface-500 text-ink-secondary border-border": variant === "default",
          "bg-accent/10 text-accent border-accent/30": variant === "accent",
          "bg-surface-700 text-ink-muted border-border/50": variant === "muted",
        },
        className
      )}
    >
      {children}
    </span>
  );
}
