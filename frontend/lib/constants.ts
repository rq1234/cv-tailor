/**
 * Shared UI constants used across multiple components.
 * Import from here instead of duplicating in each file.
 */

export const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  draft:     { label: "Draft",           className: "bg-slate-100  text-slate-600  border border-slate-200"  },
  tailoring: { label: "Processing…",    className: "bg-blue-100   text-blue-700   border border-blue-200"   },
  review:    { label: "Ready to Review", className: "bg-violet-100 text-violet-700 border border-violet-200" },
  complete:  { label: "Complete",        className: "bg-emerald-100 text-emerald-700 border border-emerald-200" },
};
