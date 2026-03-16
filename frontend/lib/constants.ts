/**
 * Shared UI constants used across multiple components.
 * Import from here instead of duplicating in each file.
 */

export const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  draft:     { label: "Draft",           className: "bg-slate-100 text-slate-500 text-[11px] font-semibold tracking-wide"             },
  tailoring: { label: "Processing…",    className: "bg-primary/10 text-primary text-[11px] font-semibold tracking-wide"              },
  review:    { label: "Ready to Review", className: "bg-violet-600 text-white text-[11px] font-semibold tracking-wide"               },
  complete:  { label: "Complete",        className: "bg-emerald-600 text-white text-[11px] font-semibold tracking-wide"              },
};
