"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { type Application, type OutcomeValue } from "@/lib/schemas";
import { useClickOutside } from "@/hooks/useClickOutside";
import { STATUS_LABEL } from "@/lib/constants";
import { OutcomeDropdown } from "./OutcomeDropdown";

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

// Deterministic hue from company name — picks a palette slot based on character codes
function getCompanyColor(name: string): { bg: string; text: string; ring: string } {
  const palettes = [
    { bg: "bg-violet-100", text: "text-violet-700", ring: "ring-violet-200" },
    { bg: "bg-sky-100",    text: "text-sky-700",    ring: "ring-sky-200" },
    { bg: "bg-emerald-100",text: "text-emerald-700",ring: "ring-emerald-200" },
    { bg: "bg-amber-100",  text: "text-amber-700",  ring: "ring-amber-200" },
    { bg: "bg-rose-100",   text: "text-rose-700",   ring: "ring-rose-200" },
    { bg: "bg-indigo-100", text: "text-indigo-700", ring: "ring-indigo-200" },
    { bg: "bg-teal-100",   text: "text-teal-700",   ring: "ring-teal-200" },
    { bg: "bg-orange-100", text: "text-orange-700", ring: "ring-orange-200" },
  ];
  const hash = name.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return palettes[hash % palettes.length];
}

function getInitials(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
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
  const [notesError, setNotesError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const status = STATUS_LABEL[app.status] ?? { label: app.status, className: "bg-slate-100 text-slate-600 border border-slate-200" };
  const statusBadgeClass = status.className;
  const date = new Date(app.created_at).toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric",
  });
  const canReview = app.status === "review" || app.status === "complete";
  const isRetailoring = retailoringId === app.id;
  const isDeletingThis = deletingId === app.id;
  const isCoverLetterLoading = coverLetterLoading && coverLetterId === app.id;

  const color = getCompanyColor(app.company_name);

  useClickOutside(menuRef, () => setIsMenuOpen(false), isMenuOpen);

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    setNotesError(null);
    try {
      await onSaveNotes(app.id, notesText);
      setEditingNotes(false);
    } catch {
      setNotesError("Failed to save notes — please try again.");
    } finally {
      setSavingNotes(false);
    }
  };

  return (
    <div className="group rounded-xl border border-border bg-card shadow-sm hover:shadow-lg hover:shadow-black/5 hover:-translate-y-px transition-all duration-200">
      {/* Card body */}
      <div className="p-4 space-y-3">
        {/* Header row */}
        <div className="flex items-start gap-3">
          {/* Initials avatar */}
          <div className={`shrink-0 h-10 w-10 rounded-xl ${color.bg} ${color.text} flex items-center justify-center text-sm font-bold tracking-tight select-none`}>
            {getInitials(app.company_name)}
          </div>

          {/* Company + role */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 min-w-0">
              <p className="font-bold tracking-tight text-foreground truncate leading-tight">{app.company_name}</p>
              {app.jd_url && (
                <a
                  href={app.jd_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-slate-400 hover:text-blue-500 transition-colors"
                  title="View job posting"
                >
                  <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                    <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                  </svg>
                </a>
              )}
            </div>
            {app.role_title && (
              <p className="text-xs text-slate-500 truncate mt-0.5">{app.role_title}</p>
            )}
          </div>

          {/* Status badge */}
          <span className={`shrink-0 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 ${statusBadgeClass}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${
              app.status === "complete" ? "bg-emerald-500" :
              app.status === "review" ? "bg-violet-500" :
              app.status === "tailoring" ? "bg-primary animate-pulse" :
              "bg-slate-400"
            }`} />
            {isRetailoring ? "Re-tailoring…" : status.label}
          </span>
        </div>

        {/* Outcome + date row */}
        <div className="flex items-center gap-2">
          <OutcomeDropdown
            value={app.outcome as OutcomeValue | null}
            appId={app.id}
            disabled={savingOutcomeId === app.id}
            variant="card"
            onChange={onOutcomeChange}
          />
          <span className="text-[11px] text-slate-400 ml-auto">{date}</span>
        </div>

        {/* Notes */}
        {editingNotes ? (
          <div className="space-y-1.5">
            <textarea
              value={notesText}
              onChange={(e) => setNotesText(e.target.value)}
              rows={2}
              placeholder="Add notes about this application…"
              autoFocus
              className="w-full rounded-lg border border-border bg-muted/50 px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-primary/15 focus:border-primary focus:bg-card transition-all duration-150"
            />
            {notesError && (
              <p className="text-[10px] text-red-600">{notesError}</p>
            )}
            <div className="flex gap-1.5">
              <button
                onClick={handleSaveNotes}
                disabled={savingNotes}
                className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {savingNotes ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => { setEditingNotes(false); setNotesError(null); }}
                className="rounded-md border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : app.notes ? (
          <button
            onClick={() => { setNotesText(app.notes ?? ""); setEditingNotes(true); }}
            className="w-full text-left"
          >
            <p className="text-xs text-slate-500 line-clamp-2 hover:text-slate-700 transition-colors">{app.notes}</p>
          </button>
        ) : null}
      </div>

      {/* Action footer */}
      <div className="flex items-center gap-1.5 border-t border-border/60 px-4 py-2.5 bg-muted/30">
        {canReview && (
          <Link
            href={`/review/${app.id}`}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary/90 transition-colors shadow-sm shadow-primary/20"
          >
            Review CV
            <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </Link>
        )}
        {canReview && (
          <button
            onClick={() => onGenerateCoverLetter(app.id)}
            disabled={isCoverLetterLoading}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground/70 hover:bg-muted hover:text-foreground transition-colors disabled:opacity-50"
          >
            {isCoverLetterLoading ? "Generating…" : "Cover Letter"}
          </button>
        )}

        {isConfirmingDelete ? (
          <span className="flex items-center gap-1 ml-auto">
            <span className="text-xs text-slate-500">Delete?</span>
            <button
              onClick={() => { onDelete(app.id); setIsConfirmingDelete(false); }}
              disabled={isDeletingThis}
              className="rounded px-2 py-0.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
            >
              {isDeletingThis ? "…" : "Yes"}
            </button>
            <button
              onClick={() => setIsConfirmingDelete(false)}
              className="rounded px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-100 transition-colors"
            >
              No
            </button>
          </span>
        ) : (
          <div className="relative ml-auto" ref={menuRef}>
            <button
              onClick={() => setIsMenuOpen((o) => !o)}
              className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              title="More options"
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zM12 10a2 2 0 11-4 0 2 2 0 014 0zM16 12a2 2 0 100-4 2 2 0 000 4z" />
              </svg>
            </button>
            {isMenuOpen && (
              <div className="absolute right-0 bottom-full mb-1.5 z-20 w-44 rounded-xl border border-border bg-card shadow-xl shadow-black/8 py-1 overflow-hidden">
                {canReview && (
                  <button
                    onClick={() => { onRetailor(app.id); setIsMenuOpen(false); }}
                    disabled={isRetailoring}
                    className="w-full px-3.5 py-2 text-left text-sm text-foreground hover:bg-muted disabled:opacity-50 transition-colors"
                  >
                    {isRetailoring ? "Re-tailoring…" : "Re-tailor"}
                  </button>
                )}
                <button
                  onClick={() => { setNotesText(app.notes ?? ""); setEditingNotes(true); setIsMenuOpen(false); }}
                  className="w-full px-3.5 py-2 text-left text-sm text-foreground hover:bg-muted transition-colors"
                >
                  {app.notes ? "Edit Notes" : "Add Notes"}
                </button>
                <Link
                  href={`/apply?company=${encodeURIComponent(app.company_name)}&role=${encodeURIComponent(app.role_title ?? "")}`}
                  onClick={() => setIsMenuOpen(false)}
                  className="block w-full px-3.5 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  Clone
                </Link>
                {canReview && (
                  <Link
                    href={`/review/${app.id}?action=download`}
                    onClick={() => setIsMenuOpen(false)}
                    className="block w-full px-3.5 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    Download PDF
                  </Link>
                )}
                <div className="my-1 mx-2 border-t border-border/60" />
                <button
                  onClick={() => { setIsConfirmingDelete(true); setIsMenuOpen(false); }}
                  className="w-full px-3.5 py-2 text-left text-sm text-red-600 hover:bg-red-50 transition-colors"
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
