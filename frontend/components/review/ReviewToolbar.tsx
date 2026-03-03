"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCheck,
  X,
  RefreshCw,
  RotateCcw,
  Download,
  ChevronDown,
  ExternalLink,
  FileText,
} from "lucide-react";

interface Counts {
  total: number;
  accepted: number;
  rejected: number;
  edited: number;
  pending: number;
}

interface ReviewToolbarProps {
  companyName?: string;
  roleTitle?: string | null;
  counts: Counts;
  recoveredFromStorage: boolean;
  saving: boolean;
  retailoring: boolean;
  showRetailorConfirm: boolean;
  onAcceptAll: () => void;
  onRejectAll: () => void;
  onReTailor: () => void;
  onConfirmReTailor: () => void;
  onCancelReTailor: () => void;
  onResetDecisions: () => void;
  onResetEdits: () => void;
  onDownloadPdf: () => void;
  onDownloadDocx: () => void;
  onOpenOverleaf: () => void;
  onDownloadLatex: () => void;
  onDismissRecovered: () => void;
}

export default function ReviewToolbar({
  companyName,
  roleTitle,
  counts,
  recoveredFromStorage,
  saving,
  retailoring,
  showRetailorConfirm,
  onAcceptAll,
  onRejectAll,
  onReTailor,
  onConfirmReTailor,
  onCancelReTailor,
  onResetDecisions,
  onResetEdits,
  onDownloadPdf,
  onDownloadDocx,
  onOpenOverleaf,
  onDownloadLatex,
  onDismissRecovered,
}: ReviewToolbarProps) {
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [resetMenuOpen, setResetMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const resetMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setExportMenuOpen(false);
      }
      if (resetMenuRef.current && !resetMenuRef.current.contains(e.target as Node)) {
        setResetMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="space-y-3">
      {/* Title row */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href="/applications"
            className="mb-1.5 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-blue-600 transition-colors"
          >
            <ArrowLeft className="h-3 w-3" /> Applications
          </Link>
          <h1 className="text-2xl font-bold leading-tight text-slate-900">
            {companyName || "Review Tailored CV"}
          </h1>
          {roleTitle && (
            <p className="text-sm text-slate-500 mt-0.5">{roleTitle}</p>
          )}
          <p className="text-xs text-slate-400 mt-1">
            {counts.total} suggestions &mdash;{" "}
            <span className="text-emerald-600 font-medium">{counts.accepted} accepted</span>,{" "}
            <span className="text-red-500 font-medium">{counts.rejected} rejected</span>,{" "}
            <span className="text-amber-600 font-medium">{counts.edited} edited</span>
            {counts.pending > 0 && (
              <>, <span className="text-orange-500 font-medium">{counts.pending} pending review</span></>
            )}
          </p>
        </div>

        {/* Action buttons — two groups */}
        <div className="flex flex-wrap items-center gap-2 mt-2 sm:mt-0">
          {/* Group A: Review actions */}
          <div className="flex items-center gap-1.5 rounded-lg border bg-white px-2 py-1.5 shadow-sm">
            <button
              onClick={onAcceptAll}
              title="Accept All"
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-emerald-50 hover:text-emerald-700 transition-colors"
            >
              <CheckCheck className="h-3.5 w-3.5" /> Accept All
            </button>
            <div className="h-4 w-px bg-slate-200" />
            <button
              onClick={onRejectAll}
              title="Reject All"
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-red-50 hover:text-red-600 transition-colors"
            >
              <X className="h-3.5 w-3.5" /> Reject All
            </button>
            <div className="h-4 w-px bg-slate-200" />
            {/* Reset dropdown */}
            <div className="relative" ref={resetMenuRef}>
              <button
                onClick={() => setResetMenuOpen((o) => !o)}
                className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <RotateCcw className="h-3.5 w-3.5" /> Reset <ChevronDown className="h-3 w-3 opacity-60" />
              </button>
              {resetMenuOpen && (
                <div className="absolute left-0 top-full mt-1 z-20 w-44 rounded-lg border bg-white shadow-lg py-1">
                  <button
                    onClick={() => { onResetDecisions(); setResetMenuOpen(false); }}
                    className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                  >
                    Reset Decisions
                  </button>
                  <button
                    onClick={() => { onResetEdits(); setResetMenuOpen(false); }}
                    className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                  >
                    Reset Edits
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Group B: Export actions */}
          <div className="flex items-center gap-1.5 rounded-lg border bg-white px-2 py-1.5 shadow-sm">
            <button
              onClick={onReTailor}
              disabled={retailoring}
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${retailoring ? "animate-spin" : ""}`} />
              {retailoring ? "Re-tailoring…" : "Re-tailor"}
            </button>
            <div className="h-4 w-px bg-slate-200" />
            {/* Download PDF — primary CTA */}
            <button
              onClick={onDownloadPdf}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 transition-colors disabled:opacity-50 shadow-sm"
            >
              <Download className="h-3.5 w-3.5" />
              {saving ? "Exporting…" : "Download PDF"}
            </button>
            {/* More export options */}
            <div className="relative" ref={exportMenuRef}>
              <button
                onClick={() => setExportMenuOpen((o) => !o)}
                disabled={saving}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 transition-colors disabled:opacity-50"
                title="More export options"
              >
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
              {exportMenuOpen && (
                <div className="absolute right-0 top-full mt-1 z-20 w-52 rounded-lg border bg-white shadow-lg py-1">
                  <button
                    onClick={() => { onOpenOverleaf(); setExportMenuOpen(false); }}
                    className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                  >
                    <ExternalLink className="h-3.5 w-3.5 text-slate-400" /> Open in Overleaf
                  </button>
                  <button
                    onClick={() => { onDownloadDocx(); setExportMenuOpen(false); }}
                    className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                  >
                    <FileText className="h-3.5 w-3.5 text-slate-400" /> Download .docx
                  </button>
                  <button
                    onClick={() => { onDownloadLatex(); setExportMenuOpen(false); }}
                    className="w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-50 flex items-center gap-2"
                  >
                    <FileText className="h-3.5 w-3.5 text-slate-400" /> Download .tex
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Recovered edits banner */}
      {recoveredFromStorage && (
        <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700">
          <span className="flex-1">Recovered unsaved edits from your last session</span>
          <button onClick={onDismissRecovered} className="text-blue-400 hover:text-blue-600 transition-colors" aria-label="Dismiss">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Re-tailor confirmation */}
      {showRetailorConfirm && (
        <div className="flex items-center gap-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span className="flex-1">Re-tailor this application? This will apply the latest tailoring logic and clear your current decisions.</span>
          <button
            onClick={onConfirmReTailor}
            className="shrink-0 rounded-md bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 transition-colors"
          >
            Confirm
          </button>
          <button
            onClick={onCancelReTailor}
            className="shrink-0 rounded-md border border-amber-300 px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100 transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
