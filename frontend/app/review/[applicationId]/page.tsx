"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useReviewPage } from "@/hooks/useReviewPage";
import AtsPanel from "@/components/review/AtsPanel";
import SimilarAppsPanel from "@/components/review/SimilarAppsPanel";
import ReviewToolbar from "@/components/review/ReviewToolbar";
import PlaceholderBanner from "@/components/review/PlaceholderBanner";
import DiffView from "@/components/review/DiffView";
import PreviewView from "@/components/review/PreviewView";

export default function ReviewPage() {
  const { applicationId } = useParams() as { applicationId: string };
  const [viewMode, setViewMode] = useState<"diff" | "preview">("diff");
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
    acceptAll,
    rejectAll,
    resetAllDecisions,
    resetAllEdits,
    dismissRecovered,
    clearExportError,
    clearSuccessMessage,
  } = useReviewPage(applicationId);

  // Auto-trigger PDF download when navigated here with ?action=download
  useEffect(() => {
    if (autoDownload && !loading && result && !hasAutoDownloaded.current) {
      hasAutoDownloaded.current = true;
      handleDownloadPdf();
    }
  }, [autoDownload, loading, result, handleDownloadPdf]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
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
      {/* Toolbar: title, back link, bulk actions, export */}
      <ReviewToolbar
        companyName={result.company_name}
        roleTitle={result.role_title}
        counts={counts}
        recoveredFromStorage={recoveredFromStorage}
        saving={saving}
        retailoring={retailoring}
        showRetailorConfirm={showRetailorConfirm}
        onAcceptAll={acceptAll}
        onRejectAll={rejectAll}
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

      {/* ATS score */}
      {result.ats_score != null && (
        <AtsPanel
          score={result.ats_score}
          warnings={result.ats_warnings ?? []}
          baselineScore={result.baseline_ats_score}
        />
      )}

      {/* Similar past applications */}
      {result.similar_applications && result.similar_applications.length > 0 && (
        <SimilarAppsPanel apps={result.similar_applications} />
      )}

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
      <div className="flex gap-1 rounded-lg bg-muted p-1 w-fit">
        <button
          onClick={() => setViewMode("diff")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            viewMode === "diff" ? "bg-white text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Diff View
        </button>
        <button
          onClick={() => setViewMode("preview")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            viewMode === "preview" ? "bg-white text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Resume Preview
        </button>
      </div>

      {viewMode === "preview" && (
        <PreviewView
          result={result}
          experienceDiffs={experienceDiffs}
          projectDiffs={projectDiffs}
          activityDiffs={activityDiffs}
          decisions={decisions}
          setBulletDecision={setBulletDecision}
          manualEdits={manualEdits}
          setManualEdit={setManualEdit}
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
        />
      )}
    </div>
  );
}
