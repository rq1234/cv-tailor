"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { OUTCOME_OPTIONS, type Application, type OutcomeValue } from "@/lib/schemas";

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  draft:     { label: "Draft",           className: "bg-slate-100 text-slate-500" },
  tailoring: { label: "Processing...",   className: "bg-amber-50 text-amber-700 border border-amber-200" },
  review:    { label: "Ready to Review", className: "bg-blue-50 text-blue-700 border border-blue-200" },
  complete:  { label: "Complete",        className: "bg-emerald-50 text-emerald-700 border border-emerald-200" },
};

interface ApplicationCardProps {
  app: Application;
  savingOutcomeId: string | null;
  deletingId: string | null;
  retailoringId: string | null;
  coverLetterId: string | null;
  coverLetterLoading: boolean;
  onOutcomeChange: (appId: string, outcome: OutcomeValue | "") => void;
  onRetailor: (appId: string) => void;
  onDelete: (appId: string) => void;
  onSaveNotes: (appId: string, notes: string) => Promise<void>;
  onGenerateCoverLetter: (appId: string) => void;
}

export default function ApplicationCard({
  app,
  savingOutcomeId,
  deletingId,
  retailoringId,
  coverLetterId,
  coverLetterLoading,
  onOutcomeChange,
  onRetailor,
  onDelete,
  onSaveNotes,
  onGenerateCoverLetter,
}: ApplicationCardProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesText, setNotesText] = useState(app.notes ?? "");
  const [savingNotes, setSavingNotes] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const status = STATUS_LABEL[app.status] ?? { label: app.status, className: "bg-gray-100 text-gray-600" };
  const date = new Date(app.created_at).toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric",
  });
  const outcomeOption = OUTCOME_OPTIONS.find((o) => o.value === app.outcome);
  const canReview = app.status === "review" || app.status === "complete";
  const isRetailoring = retailoringId === app.id;
  const isDeletingThis = deletingId === app.id;
  const isCoverLetterLoading = coverLetterLoading && coverLetterId === app.id;

  // Close menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setIsMenuOpen(false);
    };
    if (isMenuOpen) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isMenuOpen]);

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    try {
      await onSaveNotes(app.id, notesText);
      setEditingNotes(false);
    } finally {
      setSavingNotes(false);
    }
  };

  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm hover:shadow-md transition-shadow space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="font-medium truncate">{app.company_name}</p>
            {app.jd_url && (
              <a
                href={app.jd_url}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-blue-500 hover:text-blue-700"
                title="View job posting"
              >
                <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                  <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                </svg>
              </a>
            )}
          </div>
          {app.role_title && <p className="text-sm text-muted-foreground truncate">{app.role_title}</p>}
          <p className="text-xs text-muted-foreground mt-0.5">{date}</p>
        </div>
        {canReview ? (
          <Link
            href={`/review/${app.id}`}
            className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-xs font-medium hover:opacity-80 ${status.className}`}
          >
            {isRetailoring ? "Re-tailoring..." : status.label}
          </Link>
        ) : (
          <span className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}>
            {isRetailoring ? "Re-tailoring..." : status.label}
          </span>
        )}
      </div>

      {/* Outcome picker */}
      <div className="relative inline-flex items-center">
        <select
          value={app.outcome ?? ""}
          onChange={(e) => onOutcomeChange(app.id, e.target.value as OutcomeValue | "")}
          disabled={savingOutcomeId === app.id}
          className={`rounded-full border-0 py-0.5 pl-2 pr-6 text-xs font-medium appearance-none cursor-pointer focus:ring-1 focus:ring-primary disabled:opacity-50 ${
            outcomeOption ? outcomeOption.className : "text-muted-foreground bg-muted/50"
          }`}
        >
          <option value="">— set outcome —</option>
          {OUTCOME_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <svg className="pointer-events-none absolute right-1.5 h-3 w-3 text-current opacity-60" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      </div>

      {/* Notes */}
      {editingNotes ? (
        <div className="space-y-1.5">
          <textarea
            value={notesText}
            onChange={(e) => setNotesText(e.target.value)}
            rows={2}
            placeholder="Add notes about this application…"
            className="w-full rounded border px-2 py-1.5 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSaveNotes}
              disabled={savingNotes}
              className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground disabled:opacity-50"
            >
              {savingNotes ? "Saving…" : "Save"}
            </button>
            <button onClick={() => setEditingNotes(false)} className="rounded-md border px-3 py-1 text-xs hover:bg-muted">
              Cancel
            </button>
          </div>
        </div>
      ) : app.notes ? (
        <p className="text-xs text-muted-foreground line-clamp-2">{app.notes}</p>
      ) : null}

      {/* Actions row */}
      <div className="flex items-center gap-2">
        {canReview && (
          <Link href={`/review/${app.id}`} className="rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors">
            Review
          </Link>
        )}
        {canReview && (
          <button
            onClick={() => onGenerateCoverLetter(app.id)}
            disabled={isCoverLetterLoading}
            className="rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors disabled:opacity-50"
          >
            {isCoverLetterLoading ? "Generating…" : "Cover Letter"}
          </button>
        )}

        {isConfirmingDelete ? (
          <span className="flex items-center gap-1 ml-auto">
            <span className="text-xs text-muted-foreground">Delete?</span>
            <button
              onClick={() => { onDelete(app.id); setIsConfirmingDelete(false); }}
              disabled={isDeletingThis}
              className="rounded px-2 py-0.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
            >
              {isDeletingThis ? "..." : "Yes"}
            </button>
            <button onClick={() => setIsConfirmingDelete(false)} className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted">
              No
            </button>
          </span>
        ) : (
          <div className="relative ml-auto" ref={menuRef}>
            <button
              onClick={() => setIsMenuOpen((o) => !o)}
              className="rounded-md border px-2.5 py-1.5 text-xs font-medium hover:bg-muted"
              title="More options"
            >
              ···
            </button>
            {isMenuOpen && (
              <div className="absolute right-0 bottom-full mb-1 z-20 w-44 rounded-md border bg-white shadow-md py-1">
                {canReview && (
                  <button
                    onClick={() => { onRetailor(app.id); setIsMenuOpen(false); }}
                    disabled={isRetailoring}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                  >
                    {isRetailoring ? "Re-tailoring…" : "Re-tailor"}
                  </button>
                )}
                <button
                  onClick={() => { setNotesText(app.notes ?? ""); setEditingNotes(true); setIsMenuOpen(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  {app.notes ? "Edit Notes" : "Add Notes"}
                </button>
                <div className="my-1 border-t border-gray-100" />
                <button
                  onClick={() => { setIsConfirmingDelete(true); setIsMenuOpen(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                >
                  Delete
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
