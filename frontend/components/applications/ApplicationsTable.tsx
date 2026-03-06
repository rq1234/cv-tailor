"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { OUTCOME_OPTIONS, type Application, type OutcomeValue } from "@/lib/schemas";
import { STATUS_LABEL } from "@/lib/constants";

interface ApplicationsTableProps {
  applications: Application[];
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

export default function ApplicationsTable({
  applications,
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
}: ApplicationsTableProps) {
  const [overflowMenuId, setOverflowMenuId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [editingNotesId, setEditingNotesId] = useState<string | null>(null);
  const [notesText, setNotesText] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const tableRef = useRef<HTMLDivElement>(null);

  // Close overflow menus on outside click
  useEffect(() => {
    const handler = () => setOverflowMenuId(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, []);

  const startEditNotes = (app: Application) => {
    setEditingNotesId(app.id);
    setNotesText(app.notes ?? "");
  };

  const handleSaveNotes = async (appId: string) => {
    setSavingNotes(true);
    try {
      await onSaveNotes(appId, notesText);
      setEditingNotesId(null);
    } finally {
      setSavingNotes(false);
    }
  };

  return (
    <div ref={tableRef} className="overflow-hidden rounded-xl border bg-white shadow-sm">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/50">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Company</th>
            <th className="px-4 py-3 text-left font-medium">Role</th>
            <th className="px-4 py-3 text-left font-medium">Status</th>
            <th className="px-4 py-3 text-left font-medium">Outcome</th>
            <th className="px-4 py-3 text-left font-medium">Date</th>
            <th className="px-4 py-3 text-right font-medium"></th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {applications.map((app) => {
            const status = STATUS_LABEL[app.status] ?? { label: app.status, className: "bg-gray-100 text-gray-600" };
            const date = new Date(app.created_at).toLocaleDateString("en-GB", {
              day: "numeric", month: "short", year: "numeric",
            });
            const outcomeOption = OUTCOME_OPTIONS.find((o) => o.value === app.outcome);
            const canReview = app.status === "review" || app.status === "complete";
            const isRetailoring = retailoringId === app.id;
            const isDeletingThis = deletingId === app.id;
            const isConfirmingDelete = confirmDeleteId === app.id;
            const isCoverLetterLoading = coverLetterLoading && coverLetterId === app.id;

            return (
              <React.Fragment key={app.id}>
                <tr className="hover:bg-blue-50/40 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-1.5 font-medium">
                        <span>{app.company_name}</span>
                        {app.jd_url && (
                          <a
                            href={app.jd_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:text-blue-700"
                            title="View job posting"
                          >
                            <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                              <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                              <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                            </svg>
                          </a>
                        )}
                      </div>
                      {app.notes && (
                        <span className="text-xs text-muted-foreground line-clamp-1 max-w-[200px]">{app.notes}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{app.role_title || "—"}</td>
                  <td className="px-4 py-3">
                    {canReview ? (
                      <Link
                        href={`/review/${app.id}`}
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium hover:opacity-80 ${status.className}`}
                      >
                        {isRetailoring ? "Re-tailoring..." : status.label}
                      </Link>
                    ) : (
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}>
                        {isRetailoring ? "Re-tailoring..." : status.label}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
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
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{date}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {canReview && (
                        <Link
                          href={`/review/${app.id}`}
                          className="rounded-md border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
                        >
                          Review
                        </Link>
                      )}
                      {canReview && (
                        <button
                          onClick={(e) => { e.stopPropagation(); onGenerateCoverLetter(app.id); }}
                          disabled={isCoverLetterLoading}
                          className="rounded-md border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors disabled:opacity-50"
                        >
                          {isCoverLetterLoading ? "Generating…" : "Cover Letter"}
                        </button>
                      )}
                      {isConfirmingDelete ? (
                        <span className="flex items-center gap-1">
                          <span className="text-xs text-muted-foreground">Delete?</span>
                          <button
                            onClick={() => { onDelete(app.id); setConfirmDeleteId(null); }}
                            disabled={isDeletingThis}
                            className="rounded px-2 py-0.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                          >
                            {isDeletingThis ? "..." : "Yes"}
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted"
                          >
                            No
                          </button>
                        </span>
                      ) : (
                        <div className="relative">
                          <button
                            onClick={(e) => { e.stopPropagation(); setOverflowMenuId(overflowMenuId === app.id ? null : app.id); }}
                            className="rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted"
                            title="More options"
                          >
                            ···
                          </button>
                          {overflowMenuId === app.id && (
                            <div className="absolute right-0 top-full mt-1 z-20 w-48 rounded-md border bg-white shadow-md py-1">
                              {canReview && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); onRetailor(app.id); setOverflowMenuId(null); }}
                                  disabled={isRetailoring}
                                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                                >
                                  {isRetailoring ? "Re-tailoring…" : "Re-tailor"}
                                </button>
                              )}
                              <button
                                onClick={(e) => { e.stopPropagation(); startEditNotes(app); setOverflowMenuId(null); }}
                                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                              >
                                {app.notes ? "Edit Notes" : "Add Notes"}
                              </button>
                              <Link
                                href={`/apply?company=${encodeURIComponent(app.company_name)}&role=${encodeURIComponent(app.role_title ?? "")}`}
                                onClick={(e) => { e.stopPropagation(); setOverflowMenuId(null); }}
                                className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                              >
                                Clone
                              </Link>
                              {canReview && (
                                <Link
                                  href={`/review/${app.id}?action=download`}
                                  onClick={(e) => { e.stopPropagation(); setOverflowMenuId(null); }}
                                  className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                                >
                                  Download PDF
                                </Link>
                              )}
                              <div className="my-1 border-t border-gray-100" />
                              <button
                                onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(app.id); setOverflowMenuId(null); }}
                                className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                              >
                                Delete
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
                {editingNotesId === app.id && (
                  <tr className="bg-muted/20">
                    <td colSpan={6} className="px-4 py-3">
                      <div className="flex items-start gap-2">
                        <textarea
                          value={notesText}
                          onChange={(e) => setNotesText(e.target.value)}
                          rows={2}
                          placeholder="Add notes about this application…"
                          className="flex-1 rounded border px-2 py-1.5 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                        <button
                          onClick={() => handleSaveNotes(app.id)}
                          disabled={savingNotes}
                          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50 shrink-0"
                        >
                          {savingNotes ? "Saving…" : "Save"}
                        </button>
                        <button onClick={() => setEditingNotesId(null)} className="rounded-md border px-3 py-1.5 text-xs hover:bg-muted shrink-0">
                          Cancel
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
