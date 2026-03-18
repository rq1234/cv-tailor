"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useReviewPage } from "@/hooks/useReviewPage";
import { useReviewKeyboard, buildFlatBullets } from "@/hooks/useReviewKeyboard";
import ReviewToolbar from "@/components/review/ReviewToolbar";
import PlaceholderBanner from "@/components/review/PlaceholderBanner";
import DiffView from "@/components/review/DiffView";
import CvPagePreview from "@/components/review/CvPagePreview";
import { Download } from "lucide-react";
import { SkeletonBulletCard } from "@/components/ui/Skeleton";

export default function ReviewPage() {
  const { applicationId } = useParams() as { applicationId: string };
  const [viewMode, setViewMode] = useState<"diff" | "preview">(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("review-view-mode") as "diff" | "preview") ?? "diff";
    }
    return "diff";
  });

  const setAndPersistViewMode = (mode: "diff" | "preview") => {
    setViewMode(mode);
    try { localStorage.setItem("review-view-mode", mode); } catch { /* ignore */ }
  };
  const [focusedBulletIdx, setFocusedBulletIdx] = useState<number | null>(null);
  const [showStickyBar, setShowStickyBar] = useState(false);
  const autoDownload = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("action") === "download";
  const hasAutoDownloaded = useRef(false);

  const {
    result,
    loading,
    error,
    decisions,
    manualEdits,
    recoveredFromStorage,
    storageWarning,
    saving,
    retailoring,
    regeneratingBullet,
    exportError,
    successMessage,
    showRetailorConfirm,
    counts,
    experienceDiffs,
    projectDiffs,
    activityDiffs,
    setBulletDecision,
    setManualEdit,
    handleDownloadPdf,
    handleDownloadLatex,
    handleDownloadDocx,
    handleOpenOverleaf,
    handleReTailor,
    confirmReTailor,
    cancelReTailor,
    handleRegenerateBullet,
    resetAllDecisions,
    resetAllEdits,
    dismissRecovered,
    clearExportError,
    clearSuccessMessage,
  } = useReviewPage(applicationId);

  const flatBullets = buildFlatBullets(experienceDiffs, projectDiffs, activityDiffs);
  const focusedBullet = focusedBulletIdx !== null ? flatBullets[focusedBulletIdx] ?? null : null;

  useReviewKeyboard({
    flatBullets,
    focusedIdx: focusedBulletIdx,
    setFocusedIdx: setFocusedBulletIdx,
    setBulletDecision,
    decisions,
  });

  // Auto-trigger PDF download when navigated here with ?action=download
  useEffect(() => {
    if (autoDownload && !loading && result && !hasAutoDownloaded.current) {
      hasAutoDownloaded.current = true;
      handleDownloadPdf();
    }
  }, [autoDownload, loading, result, handleDownloadPdf]);

  // Sticky bar on scroll
  useEffect(() => {
    const handleScroll = () => setShowStickyBar(window.scrollY > 120);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Toolbar skeleton */}
        <div className="space-y-2">
          <div className="h-3 w-24 animate-pulse rounded bg-slate-200" />
          <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
          <div className="h-3 w-64 animate-pulse rounded bg-slate-200" />
          <div className="h-1.5 w-72 animate-pulse rounded-full bg-slate-200" />
        </div>
        {/* Bullet card skeletons */}
        {[0, 1].map((i) => <SkeletonBulletCard key={i} />)}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <p className="text-sm text-red-700">{error}</p>
        <p className="mt-2 text-xs text-red-500">
          Make sure you&apos;ve run the tailoring pipeline first from the Apply page.
        </p>
      </div>
    );
  }

  if (!result || !result.diff_json) {
    return (
      <div className="text-center py-20">
        <p className="text-muted-foreground">No tailoring results found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Sticky summary bar — slides in on scroll */}
      <div
        className={`fixed top-14 left-0 right-0 z-30 border-b border-border/60 bg-background/95 backdrop-blur-md transition-transform duration-200 ${
          showStickyBar ? "translate-y-0" : "-translate-y-full"
        }`}
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-2">
          <div className="flex items-center gap-3 text-xs text-slate-500 min-w-0">
            <span className="font-medium text-slate-700 truncate">{result.company_name}</span>
            {counts.total > 0 && (
              <>
                <span className="text-emerald-600 font-medium">{counts.accepted + counts.pending} using AI</span>
                {counts.rejected > 0 && <span className="text-slate-500 font-medium">{counts.rejected} reverted</span>}
                {counts.edited > 0 && <span className="text-amber-600 font-medium">{counts.edited} edited</span>}
              </>
            )}
          </div>
          <button
            onClick={handleDownloadPdf}
            disabled={saving}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {saving ? "Exporting…" : "Download PDF"}
          </button>
        </div>
      </div>

      {/* Toolbar: title, back link, bulk actions, export */}
      <ReviewToolbar
        companyName={result.company_name}
        roleTitle={result.role_title}
        counts={counts}
        recoveredFromStorage={recoveredFromStorage}
        saving={saving}
        retailoring={retailoring}
        showRetailorConfirm={showRetailorConfirm}
        onReTailor={handleReTailor}
        onConfirmReTailor={confirmReTailor}
        onCancelReTailor={cancelReTailor}
        onResetDecisions={resetAllDecisions}
        onResetEdits={resetAllEdits}
        onDownloadPdf={handleDownloadPdf}
        onDownloadDocx={handleDownloadDocx}
        onOpenOverleaf={handleOpenOverleaf}
        onDownloadLatex={handleDownloadLatex}
        onDismissRecovered={dismissRecovered}
      />

      {/* Placeholder fill assistant */}
      <PlaceholderBanner diffJson={result.diff_json} onApply={setBulletDecision} />

      {/* Storage quota warning */}
      {storageWarning && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Your browser storage is full — edits won&apos;t be saved locally. Consider clearing browser storage or using a different browser.
        </div>
      )}

      {/* Success / error feedback */}
      {successMessage && (
        <div className="flex items-center justify-between rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          <span>{successMessage}</span>
          <button onClick={clearSuccessMessage} className="text-green-400 hover:text-green-600" aria-label="Dismiss">✕</button>
        </div>
      )}
      {exportError && (
        <div className="flex items-center justify-between rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{exportError}</span>
          <button onClick={clearExportError} className="text-red-400 hover:text-red-600" aria-label="Dismiss">✕</button>
        </div>
      )}

      {/* View mode toggle */}
      <div className="flex gap-1 rounded-xl bg-muted border border-border/40 p-1 w-fit">
        <button
          onClick={() => setAndPersistViewMode("diff")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            viewMode === "diff" ? "bg-card text-foreground shadow-md shadow-black/6" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Diff View
        </button>
        <button
          onClick={() => setAndPersistViewMode("preview")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            viewMode === "preview" ? "bg-card text-foreground shadow-md shadow-black/6" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Resume Preview
        </button>
      </div>

      {viewMode === "preview" && (
        <CvPagePreview
          result={result}
          experienceDiffs={experienceDiffs}
          projectDiffs={projectDiffs}
          activityDiffs={activityDiffs}
          decisions={decisions}
          manualEdits={manualEdits}
        />
      )}

      {viewMode === "diff" && (
        <DiffView
          result={result}
          experienceDiffs={experienceDiffs}
          projectDiffs={projectDiffs}
          activityDiffs={activityDiffs}
          decisions={decisions}
          setBulletDecision={setBulletDecision}
          manualEdits={manualEdits}
          setManualEdit={setManualEdit}
          regeneratingBullet={regeneratingBullet}
          onRegenerateBullet={handleRegenerateBullet}
          focusedBullet={focusedBullet}
        />
      )}

    </div>
  );
}
