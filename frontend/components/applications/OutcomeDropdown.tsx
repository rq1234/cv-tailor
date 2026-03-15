"use client";

import { OUTCOME_OPTIONS, type OutcomeValue } from "@/lib/schemas";

interface OutcomeDropdownProps {
  value: OutcomeValue | "" | null | undefined;
  appId: string;
  disabled?: boolean;
  /** "card" = pill with border (ApplicationCard); "table" = borderless (ApplicationsTable) */
  variant?: "card" | "table";
  onChange: (appId: string, outcome: OutcomeValue | "") => void;
}

export function OutcomeDropdown({
  value,
  appId,
  disabled = false,
  variant = "card",
  onChange,
}: OutcomeDropdownProps) {
  const outcomeOption = OUTCOME_OPTIONS.find((o) => o.value === value);

  const baseClass =
    variant === "card"
      ? "rounded-full py-0.5 pl-2.5 pr-6 text-[11px] font-medium appearance-none cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50 border"
      : "rounded-full border-0 py-0.5 pl-2 pr-6 text-xs font-medium appearance-none cursor-pointer focus:ring-1 focus:ring-primary disabled:opacity-50";

  const colorClass = outcomeOption
    ? outcomeOption.className
    : variant === "card"
    ? "text-slate-500 bg-slate-50 border-slate-200"
    : "text-muted-foreground bg-muted/50";

  return (
    <div className="relative inline-flex items-center">
      <select
        value={value ?? ""}
        onChange={(e) => onChange(appId, e.target.value as OutcomeValue | "")}
        disabled={disabled}
        className={`${baseClass} ${colorClass}`}
      >
        <option value="">{variant === "card" ? "— outcome —" : "— set outcome —"}</option>
        {OUTCOME_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <svg
        className="pointer-events-none absolute right-1.5 h-2.5 w-2.5 text-current opacity-50"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fillRule="evenodd"
          d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
          clipRule="evenodd"
        />
      </svg>
    </div>
  );
}
