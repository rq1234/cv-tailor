/**
 * Shared UI constants used across multiple components.
 * Import from here instead of duplicating in each file.
 */

export const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  draft:     { label: "Draft",           className: "bg-muted text-muted-foreground text-[11px] font-semibold tracking-wide"           },
  tailoring: { label: "Processing…",    className: "bg-primary/10 text-primary text-[11px] font-semibold tracking-wide"              },
  review:    { label: "Ready to Review", className: "bg-violet-100 text-violet-700 text-[11px] font-semibold tracking-wide"           },
  complete:  { label: "Complete",        className: "bg-emerald-100 text-emerald-700 text-[11px] font-semibold tracking-wide"         },
};
