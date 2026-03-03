"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, TrendingUp, TrendingDown } from "lucide-react";
import type { AtsWarning } from "./types";

interface AtsPanelProps {
  score: number;
  warnings: AtsWarning[];
  baselineScore?: number;
}

export default function AtsPanel({ score, warnings, baselineScore }: AtsPanelProps) {
  const [open, setOpen] = useState(false);

  const isGood = score >= 80;
  const isOk = score >= 60;

  const borderClass = isGood
    ? "border-l-emerald-500"
    : isOk
    ? "border-l-amber-400"
    : "border-l-red-400";

  const scoreClass = isGood
    ? "text-emerald-700"
    : isOk
    ? "text-amber-700"
    : "text-red-600";

  const label = isGood ? "ATS Compatible" : isOk ? "Needs Review" : "ATS Issues";
  const labelClass = isGood
    ? "text-emerald-600 bg-emerald-50 border border-emerald-200"
    : isOk
    ? "text-amber-600 bg-amber-50 border border-amber-200"
    : "text-red-600 bg-red-50 border border-red-200";

  const delta = baselineScore != null ? score - baselineScore : null;
  const improved = delta != null && delta > 0;

  return (
    <div className={`rounded-xl border bg-white shadow-sm border-l-4 ${borderClass} px-4 py-3`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Large score number */}
          <div className="text-center">
            <div className={`text-3xl font-bold tabular-nums leading-none ${scoreClass}`}>{score}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">/100</div>
          </div>

          <div className="space-y-1">
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${labelClass}`}>
              {label}
            </span>
            {/* Delta badge */}
            {delta != null && delta !== 0 && (
              <div className={`flex items-center gap-0.5 text-xs font-medium ${improved ? "text-emerald-600" : "text-red-500"}`}>
                {improved ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                {improved ? "+" : ""}{delta} pts from baseline
              </div>
            )}
            {warnings.length > 0 && (
              <div className="flex items-center gap-1 text-xs text-slate-400">
                <AlertTriangle className="h-3 w-3" />
                {warnings.length} warning{warnings.length !== 1 ? "s" : ""}
              </div>
            )}
          </div>
        </div>

        {warnings.length > 0 && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 transition-colors"
          >
            {open ? (
              <><ChevronUp className="h-3.5 w-3.5" /> Hide</>
            ) : (
              <><ChevronDown className="h-3.5 w-3.5" /> Show warnings</>
            )}
          </button>
        )}
      </div>

      {open && warnings.length > 0 && (
        <ul className="mt-3 space-y-2 border-t border-slate-100 pt-3">
          {warnings.map((w, i) => (
            <li key={i} className="flex items-start gap-2 text-xs">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
              <div className="min-w-0">
                <span className="font-semibold text-slate-700">{w.field}: </span>
                <span className="text-slate-600">{w.issue}</span>
                {w.suggestion && (
                  <span className="ml-1.5 text-slate-400">→ {w.suggestion}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
