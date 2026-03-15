"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useApplicationsList } from "@/hooks/useApplicationsList";
import { OUTCOME_OPTIONS } from "@/lib/schemas";
import ApplicationStats from "@/components/applications/ApplicationStats";
import GapRecommendations from "@/components/applications/GapRecommendations";
import CoverLetterModal from "@/components/applications/CoverLetterModal";
import ApplicationCard from "@/components/applications/ApplicationCard";
import ApplicationsTable from "@/components/applications/ApplicationsTable";
import ApplicationKanban from "@/components/applications/ApplicationKanban";
import { SkeletonCard, ErrorBanner } from "@/components/ui/Skeleton";
import { LayoutGrid, List } from "lucide-react";

export default function ApplicationsPage() {
  const [search, setSearch] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "kanban">(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("applications-view-mode") as "list" | "kanban") ?? "list";
    }
    return "list";
  });

  const setAndPersistViewMode = (mode: "list" | "kanban") => {
    setViewMode(mode);
    try { localStorage.setItem("applications-view-mode", mode); } catch { /* ignore */ }
  };

  const {
    applications,
    stats,
    gapRecs,
    loading,
    error,
    statsError,
    savingOutcomeId,
    deletingId,
    retailoringId,
    coverLetterId,
    coverLetterText,
    coverLetterParts,
    coverLetterLoading,
    coverLetterTimedOut,
    fetchApplications,
    handleOutcomeChange,
    handleRetailor,
    handleDelete,
    handleSaveNotes,
    handleGenerateCoverLetter,
    clearCoverLetter,
  } = useApplicationsList();

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  const filteredApplications = useMemo(() => {
    const q = search.trim().toLowerCase();
    return applications.filter((app) => {
      const matchesSearch =
        !q ||
        app.company_name.toLowerCase().includes(q) ||
        (app.role_title ?? "").toLowerCase().includes(q);
      const matchesOutcome =
        !outcomeFilter || app.outcome === outcomeFilter;
      return matchesSearch && matchesOutcome;
    });
  }, [applications, search, outcomeFilter]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-36 animate-pulse rounded bg-slate-200" />
          <div className="h-9 w-36 animate-pulse rounded-md bg-slate-200" />
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-xl border bg-white px-4 py-4 shadow-sm space-y-2 animate-pulse">
              <div className="h-8 w-8 rounded-lg bg-slate-200" />
              <div className="h-7 w-1/2 rounded bg-slate-200" />
              <div className="h-3 w-1/3 rounded bg-slate-200" />
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => <SkeletonCard key={i} />)}
        </div>
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

  const sharedProps = {
    savingOutcomeId,
    deletingId,
    retailoringId,
    coverLetterId,
    coverLetterLoading,
    onOutcomeChange: handleOutcomeChange,
    onRetailor: handleRetailor,
    onDelete: handleDelete,
    onSaveNotes: handleSaveNotes,
    onGenerateCoverLetter: handleGenerateCoverLetter,
  };

  return (
    <div className="space-y-6">
      {/* Cover letter modal */}
      {coverLetterId && (
        <CoverLetterModal
          text={coverLetterText}
          parts={coverLetterParts}
          loading={coverLetterLoading}
          timedOut={coverLetterTimedOut}
          onRetry={() => handleGenerateCoverLetter(coverLetterId)}
          onClose={clearCoverLetter}
        />
      )}

      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Applications</h1>
        <Link
          href="/apply"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          New Application
        </Link>
      </div>

      {/* Stats load warning */}
      {statsError && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Stats couldn&apos;t load — some metrics may be unavailable.{" "}
          <button onClick={fetchApplications} className="underline hover:text-amber-900">Retry</button>
        </div>
      )}

      {/* Stats dashboard */}
      {stats && stats.total > 0 && <ApplicationStats stats={stats} />}

      {/* Skills gap recommendations */}
      {gapRecs.length > 0 && <GapRecommendations recs={gapRecs} />}

      {/* Application list */}
      {applications.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {/* Search + filter + view toggle */}
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by company or role…"
              className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">All outcomes</option>
              {OUTCOME_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            {/* View mode toggle */}
            <div className="flex gap-1 rounded-lg bg-muted p-1 shrink-0">
              <button
                onClick={() => setAndPersistViewMode("list")}
                title="List view"
                className={`rounded-md p-1.5 transition-colors ${viewMode === "list" ? "bg-white shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              >
                <List className="h-4 w-4" />
              </button>
              <button
                onClick={() => setAndPersistViewMode("kanban")}
                title="Kanban view"
                className={`rounded-md p-1.5 transition-colors ${viewMode === "kanban" ? "bg-white shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              >
                <LayoutGrid className="h-4 w-4" />
              </button>
            </div>
          </div>

          {filteredApplications.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No applications match your search.{" "}
              <button onClick={() => { setSearch(""); setOutcomeFilter(""); }} className="underline hover:text-foreground">
                Clear filters
              </button>
            </p>
          ) : viewMode === "kanban" ? (
            <ApplicationKanban applications={filteredApplications} />
          ) : (
            <>
              {/* Mobile */}
              <div className="flex flex-col gap-3 sm:hidden">
                {filteredApplications.map((app) => (
                  <ApplicationCard key={app.id} app={app} {...sharedProps} />
                ))}
              </div>
              {/* Desktop */}
              <div className="hidden sm:block">
                <ApplicationsTable applications={filteredApplications} {...sharedProps} />
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border-2 border-dashed border-slate-200 bg-white p-8 shadow-sm sm:p-12">
      <p className="text-center text-xl font-bold text-slate-800">Get started with CV Tailor</p>
      <p className="text-center mt-1.5 text-sm text-slate-500 mb-10">
        AI-tailored CVs for every job — in three simple steps.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
        <div className="rounded-xl border bg-blue-50/50 p-5 text-center hover:shadow-sm transition-shadow">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-sm font-bold text-white shadow-sm shadow-blue-200">1</div>
          <p className="text-sm font-semibold text-slate-800">Upload your CV</p>
          <p className="mt-1.5 text-xs text-slate-500">Go to <Link href="/upload" className="text-blue-600 underline-offset-2 hover:underline">Upload</Link> to import your existing CV</p>
        </div>
        <div className="rounded-xl border bg-violet-50/50 p-5 text-center hover:shadow-sm transition-shadow">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600 text-sm font-bold text-white shadow-sm shadow-violet-200">2</div>
          <p className="text-sm font-semibold text-slate-800">Create an application</p>
          <p className="mt-1.5 text-xs text-slate-500">Paste the job description and let AI tailor your CV</p>
        </div>
        <div className="rounded-xl border bg-emerald-50/50 p-5 text-center hover:shadow-sm transition-shadow">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-sm font-bold text-white shadow-sm shadow-emerald-200">3</div>
          <p className="text-sm font-semibold text-slate-800">Download tailored PDF</p>
          <p className="mt-1.5 text-xs text-slate-500">Review suggestions, accept changes, and export</p>
        </div>
      </div>
      <div className="flex justify-center">
        <Link
          href="/apply"
          className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors shadow-sm shadow-blue-200"
        >
          New Application
        </Link>
      </div>
    </div>
  );
}
