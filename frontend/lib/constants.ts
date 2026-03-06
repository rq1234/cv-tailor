/**
 * Shared UI constants used across multiple components.
 * Import from here instead of duplicating in each file.
 */

export const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  draft:     { label: "Draft",           className: "bg-slate-100 text-slate-500" },
  tailoring: { label: "Processing...",   className: "bg-amber-50 text-amber-700 border border-amber-200" },
  review:    { label: "Ready to Review", className: "bg-blue-50 text-blue-700 border border-blue-200" },
  complete:  { label: "Complete",        className: "bg-emerald-50 text-emerald-700 border border-emerald-200" },
};
