"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { applicationSchema, OUTCOME_OPTIONS, type Application, type OutcomeValue } from "@/lib/schemas";
import { z } from "zod";

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  draft:      { label: "Draft",           className: "bg-gray-100 text-gray-600" },
  tailoring:  { label: "Processing...",   className: "bg-yellow-50 text-yellow-700" },
  review:     { label: "Ready to Review", className: "bg-blue-50 text-blue-700" },
  complete:   { label: "Complete",        className: "bg-green-50 text-green-700" },
};

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingOutcome, setSavingOutcome] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [retailoringId, setRetailoringId] = useState<string | null>(null);

  const fetchApplications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Application[]>("/api/applications");
      setApplications(z.array(applicationSchema).parse(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load applications");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  const handleOutcomeChange = async (appId: string, outcome: OutcomeValue | "") => {
    setSavingOutcome(appId);
    try {
      await api.patch(`/api/applications/${appId}`, { outcome: outcome || null });
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, outcome: outcome || null } : a))
      );
    } finally {
      setSavingOutcome(null);
    }
  };

  const handleRetailor = async (appId: string) => {
    setRetailoringId(appId);
    try {
      await api.post(`/api/tailor/re-tailor/${appId}`);
      await fetchApplications();
    } catch {
      // fetchApplications will reflect actual state regardless
    } finally {
      setRetailoringId(null);
    }
  };

  const handleDelete = async (appId: string) => {
    setDeleting(appId);
    try {
      await api.delete(`/api/applications/${appId}`);
      setApplications((prev) => prev.filter((a) => a.id !== appId));
    } finally {
      setDeleting(null);
      setConfirmDelete(null);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <p className="text-sm text-red-700">{error}</p>
        <button onClick={fetchApplications} className="mt-3 rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Applications</h1>
        <Link
          href="/apply"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          New Application
        </Link>
      </div>

      {/* Funnel stats — only when at least one outcome is set */}
      {applications.length > 0 && applications.some((a) => a.outcome) && (() => {
        const counts: Record<string, number> = {};
        for (const a of applications) {
          if (a.outcome) counts[a.outcome] = (counts[a.outcome] ?? 0) + 1;
        }
        const pills = OUTCOME_OPTIONS.filter((o) => counts[o.value]);
        return (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-muted-foreground font-medium">Funnel:</span>
            {pills.map((o) => (
              <span key={o.value} className={`rounded-full px-2.5 py-0.5 font-medium ${o.className}`}>
                {o.label}: {counts[o.value]}
              </span>
            ))}
          </div>
        );
      })()}

      {applications.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
          <p className="text-lg text-muted-foreground">No applications yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Start a new application to tailor your CV for a specific role.
          </p>
          <Link
            href="/apply"
            className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            New Application
          </Link>
        </div>
      ) : (
        <>
          {/* Mobile card list */}
          <div className="flex flex-col gap-3 sm:hidden">
            {applications.map((app) => {
              const status = STATUS_LABEL[app.status] ?? { label: app.status, className: "bg-gray-100 text-gray-600" };
              const date = new Date(app.created_at).toLocaleDateString("en-GB", {
                day: "numeric", month: "short", year: "numeric",
              });
              const outcomeOption = OUTCOME_OPTIONS.find((o) => o.value === app.outcome);
              const isConfirmingDelete = confirmDelete === app.id;
              const isDeletingThis = deleting === app.id;
              const isRetailoring = retailoringId === app.id;
              const canRetailor = app.status === "review" || app.status === "complete";

              return (
                <div key={app.id} className="rounded-lg border p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium truncate">{app.company_name}</p>
                      {app.role_title && (
                        <p className="text-sm text-muted-foreground truncate">{app.role_title}</p>
                      )}
                      <p className="text-xs text-muted-foreground mt-0.5">{date}</p>
                    </div>
                    <span className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}>
                      {isRetailoring ? "Re-tailoring..." : status.label}
                    </span>
                  </div>

                  <div className="relative inline-flex items-center">
                    <select
                      value={app.outcome ?? ""}
                      onChange={(e) => handleOutcomeChange(app.id, e.target.value as OutcomeValue | "")}
                      disabled={savingOutcome === app.id}
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

                  <div className="flex flex-wrap items-center gap-2">
                    {canRetailor && (
                      <Link
                        href={`/review/${app.id}`}
                        className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted"
                      >
                        Review
                      </Link>
                    )}
                    {canRetailor && (
                      <button
                        onClick={() => handleRetailor(app.id)}
                        disabled={isRetailoring}
                        className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
                      >
                        {isRetailoring ? "..." : "Re-tailor"}
                      </button>
                    )}
                    {isConfirmingDelete ? (
                      <span className="flex items-center gap-1">
                        <span className="text-xs text-muted-foreground">Delete?</span>
                        <button
                          onClick={() => handleDelete(app.id)}
                          disabled={isDeletingThis}
                          className="rounded px-2 py-0.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                        >
                          {isDeletingThis ? "..." : "Yes"}
                        </button>
                        <button
                          onClick={() => setConfirmDelete(null)}
                          className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted"
                        >
                          No
                        </button>
                      </span>
                    ) : (
                      <button
                        onClick={() => setConfirmDelete(app.id)}
                        className="rounded border border-transparent px-2 py-1.5 text-xs text-muted-foreground hover:border-red-200 hover:text-red-600 hover:bg-red-50"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Desktop table */}
          <div className="hidden sm:block overflow-hidden rounded-lg border">
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
                  const isConfirmingDelete = confirmDelete === app.id;
                  const isDeletingThis = deleting === app.id;
                  const isRetailoring = retailoringId === app.id;
                  const canRetailor = app.status === "review" || app.status === "complete";

                  return (
                    <tr key={app.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3 font-medium">{app.company_name}</td>
                      <td className="px-4 py-3 text-muted-foreground">{app.role_title || "—"}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}>
                          {isRetailoring ? "Re-tailoring..." : status.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="relative inline-flex items-center">
                          <select
                            value={app.outcome ?? ""}
                            onChange={(e) => handleOutcomeChange(app.id, e.target.value as OutcomeValue | "")}
                            disabled={savingOutcome === app.id}
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
                          {canRetailor && (
                            <Link
                              href={`/review/${app.id}`}
                              className="rounded-md border px-3 py-1 text-xs font-medium hover:bg-muted"
                            >
                              Review
                            </Link>
                          )}
                          {canRetailor && (
                            <button
                              onClick={() => handleRetailor(app.id)}
                              disabled={isRetailoring}
                              className="rounded-md border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
                              title="Re-run tailoring with latest AI improvements"
                            >
                              {isRetailoring ? "..." : "Re-tailor"}
                            </button>
                          )}
                          {isConfirmingDelete ? (
                            <span className="flex items-center gap-1">
                              <span className="text-xs text-muted-foreground">Delete?</span>
                              <button
                                onClick={() => handleDelete(app.id)}
                                disabled={isDeletingThis}
                                className="rounded px-2 py-0.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                              >
                                {isDeletingThis ? "..." : "Yes"}
                              </button>
                              <button
                                onClick={() => setConfirmDelete(null)}
                                className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted"
                              >
                                No
                              </button>
                            </span>
                          ) : (
                            <button
                              onClick={() => setConfirmDelete(app.id)}
                              className="rounded border border-transparent px-2 py-1 text-xs text-muted-foreground hover:border-red-200 hover:text-red-600 hover:bg-red-50"
                              title="Delete application"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
