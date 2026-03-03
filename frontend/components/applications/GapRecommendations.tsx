"use client";

import { useState } from "react";
import { Lightbulb, ChevronDown, ChevronUp } from "lucide-react";
import type { GapRec } from "@/hooks/useApplicationsList";

export default function GapRecommendations({ recs }: { recs: GapRec[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 shadow-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-amber-800"
      >
        <span className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-amber-500" />
          Skills to Build
          <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-bold text-amber-800">
            {recs.length} gap{recs.length !== 1 ? "s" : ""}
          </span>
        </span>
        {open ? (
          <ChevronUp className="h-4 w-4 text-amber-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-amber-500" />
        )}
      </button>
      {open && (
        <div className="border-t border-amber-200 px-4 py-3 space-y-2.5">
          {recs.map((rec, i) => (
            <div key={i} className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <span className="font-semibold text-amber-900 text-sm">{rec.gap}</span>
                {rec.companies.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {rec.companies.slice(0, 3).map((c) => (
                      <span key={c} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700 border border-amber-200">
                        {c}
                      </span>
                    ))}
                    {rec.companies.length > 3 && (
                      <span className="text-xs text-amber-500">+{rec.companies.length - 3} more</span>
                    )}
                  </div>
                )}
              </div>
              <span className="shrink-0 rounded-full bg-amber-200 px-2.5 py-0.5 text-xs font-semibold text-amber-800 capitalize whitespace-nowrap">
                {rec.domain} · {rec.count}×
              </span>
            </div>
          ))}
          <p className="text-xs text-amber-600 pt-1 border-t border-amber-200 mt-3">
            These requirements appeared as gaps across your recent applications. Consider upskilling here.
          </p>
        </div>
      )}
    </div>
  );
}
