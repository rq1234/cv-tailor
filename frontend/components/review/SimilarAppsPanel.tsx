"use client";

import { useState } from "react";
import Link from "next/link";
import type { SimilarApplication } from "./types";

export default function SimilarAppsPanel({ apps }: { apps: SimilarApplication[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-md border border-blue-100 bg-blue-50 text-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-medium text-blue-700"
      >
        <span>Similar past applications ({apps.length})</span>
        <span>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="border-t border-blue-100 px-4 py-2 space-y-1.5">
          {apps.map((a) => (
            <div key={a.id} className="flex items-center justify-between text-xs">
              <div>
                <span className="font-medium text-blue-900">{a.company_name}</span>
                {a.role_title && <span className="text-blue-700 ml-1">— {a.role_title}</span>}
                {a.domain && <span className="ml-1.5 text-blue-500 capitalize">({a.domain})</span>}
              </div>
              <div className="flex items-center gap-3">
                {a.ats_score != null && <span className="text-blue-600">ATS {a.ats_score}</span>}
                <Link
                  href={`/review/${a.id}`}
                  className="rounded px-2 py-0.5 text-xs bg-blue-100 text-blue-700 hover:bg-blue-200"
                >
                  View →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
