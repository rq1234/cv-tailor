"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import DiffView from "@/components/review/DiffView";
import PreviewView from "@/components/review/PreviewView";
import {
  type AtsWarning,
  type BulletDecision,
  type BulletState,
  type TailorResult,
  bulletText,
  sortByDateDesc,
} from "@/components/review/types";

function AtsPanel({ score, warnings }: { score: number; warnings: AtsWarning[] }) {
  const [open, setOpen] = useState(false);
  const colourClass =
    score >= 80 ? "border-green-200 bg-green-50 text-green-800"
    : score >= 60 ? "border-amber-200 bg-amber-50 text-amber-800"
    : "border-red-200 bg-red-50 text-red-800";
  const badgeClass =
    score >= 80 ? "bg-green-100 text-green-700"
    : score >= 60 ? "bg-amber-100 text-amber-700"
    : "bg-red-100 text-red-700";
  const label = score >= 80 ? "ATS Compatible" : score >= 60 ? "Needs Review" : "ATS Issues";

  return (
    <div className={`rounded-md border px-4 py-3 text-sm ${colourClass}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${badgeClass}`}>
            ATS {score}/100
          </span>
          <span className="font-medium">{label}</span>
          {warnings.length > 0 && (
            <span className="text-xs opacity-70">{warnings.length} warning{warnings.length !== 1 ? "s" : ""}</span>
          )}
        </div>
        {warnings.length > 0 && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="text-xs underline-offset-2 hover:underline opacity-70"
          >
            {open ? "Hide" : "Show warnings"}
          </button>
        )}
      </div>
      {open && warnings.length > 0 && (
        <ul className="mt-3 space-y-2 border-t border-current/10 pt-3">
          {warnings.map((w, i) => (
            <li key={i} className="grid grid-cols-[auto_1fr] gap-x-3 text-xs">
              <span className="font-medium opacity-80">{w.field}</span>
              <div>
                <span>{w.issue}</span>
                {w.suggestion && (
                  <span className="ml-2 opacity-70">→ {w.suggestion}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ReviewPage() {
  const params = useParams();
  const applicationId = params.applicationId as string;
  const [result, setResult] = useState<TailorResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [retailoring, setRetailoring] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showRetailorConfirm, setShowRetailorConfirm] = useState(false);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [resetMenuOpen, setResetMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const resetMenuRef = useRef<HTMLDivElement>(null);
  const [regeneratingBullet, setRegeneratingBullet] = useState<{ expId: string; idx: number } | null>(null);
  const [viewMode, setViewMode] = useState<"diff" | "preview">("diff");
  const [decisions, setDecisions] = useState<Record<string, Record<number, BulletState>>>({});
  const [manualEdits, setManualEdits] = useState<Record<string, string>>({});
  const [recoveredFromStorage, setRecoveredFromStorage] = useState(false);

  // localStorage key unique to this application
  const storageKey = `cv-edits-${applicationId}`;
  // Debounce timer ref — prevents excessive localStorage writes on rapid state changes
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSetManualEdit = (key: string, value: string) => {
    setManualEdits((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const fetchResult = useCallback(async () => {
    try {
      const data = await api.get<TailorResult>(`/api/tailor/result/${applicationId}`);
      setResult(data);

      const initial: Record<string, Record<number, BulletState>> = {};
      for (const [expId, diff] of Object.entries(data.diff_json || {})) {
        initial[expId] = {};
        for (let i = 0; i < diff.suggested_bullets.length; i++) {
          initial[expId][i] = { decision: "accept" };
        }
      }
      
      // Try to restore from localStorage
      try {
        const stored = localStorage.getItem(storageKey);
        if (stored) {
          const { decisions: storedDecisions, manualEdits: storedEdits } = JSON.parse(stored);
          // Merge localStorage decisions with fresh initial decisions
          const mergedDecisions = { ...initial, ...storedDecisions };
          setDecisions(mergedDecisions);
          setManualEdits(storedEdits || {});
          setRecoveredFromStorage(true);
        } else {
          setDecisions(initial);
        }
      } catch (e) {
        // If localStorage parse fails, just use initial
        console.warn("Failed to restore from localStorage:", e);
        setDecisions(initial);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load result");
    } finally {
      setLoading(false);
    }
  }, [applicationId, storageKey]);

  useEffect(() => {
    fetchResult();
  }, [fetchResult]);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node))
        setExportMenuOpen(false);
      if (resetMenuRef.current && !resetMenuRef.current.contains(e.target as Node))
        setResetMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Auto-save to localStorage with 300ms debounce to prevent excessive writes
  useEffect(() => {
    if (!decisions || Object.keys(decisions).length === 0) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      try {
        const toStore = { decisions, manualEdits };
        localStorage.setItem(storageKey, JSON.stringify(toStore));
      } catch (e) {
        console.warn("Failed to save to localStorage:", e);
      }
    }, 300);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [decisions, manualEdits, storageKey]);

  const setBulletDecision = (
    expId: string,
    bulletIndex: number,
    decision: BulletDecision,
    editedText?: string
  ) => {
    setDecisions((prev) => ({
      ...prev,
      [expId]: {
        ...prev[expId],
        [bulletIndex]: {
          decision,
          editedText: editedText !== undefined ? editedText : prev[expId]?.[bulletIndex]?.editedText,
        },
      },
    }));
  };

  const resetAllDecisions = () => {
    if (!result) return;
    const initial: Record<string, Record<number, BulletState>> = {};
    for (const [expId, diff] of Object.entries(result.diff_json || {})) {
      initial[expId] = {};
      for (let i = 0; i < diff.suggested_bullets.length; i++) {
        initial[expId][i] = { decision: "accept" };
      }
    }
    setDecisions(initial);
  };

  const resetAllEdits = () => {
    setManualEdits({});
  };

  const acceptAll = () => {
    setDecisions((prev) => {
      const next: typeof prev = {};
      for (const [expId, expDecs] of Object.entries(prev)) {
        next[expId] = {};
        for (const idx of Object.keys(expDecs)) {
          next[expId][Number(idx)] = { decision: "accept" };
        }
      }
      return next;
    });
  };

  const rejectAll = () => {
    setDecisions((prev) => {
      const next: typeof prev = {};
      for (const [expId, expDecs] of Object.entries(prev)) {
        next[expId] = {};
        for (const idx of Object.keys(expDecs)) {
          next[expId][Number(idx)] = { decision: "reject" };
        }
      }
      return next;
    });
  };

  const handleDownloadLatex = async () => {
    if (!result) return;
    setSaving(true);
    setExportError(null);
    setSuccessMessage(null);
    try {
      const changes = buildChanges();
      if (changes) {
        await api.put(`/api/tailor/cv-versions/${result.cv_version_id}/accept-changes`, {
          accepted_changes: changes.acceptedChanges,
          rejected_changes: changes.rejectedChanges,
        });
      }
      const { blob, filename } = await api.downloadFile(`/api/export/latex/${result.cv_version_id}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "cv.tex";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download failed:", err);
      setExportError("Failed to download LaTeX file.");
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!result) return;
    setSaving(true);
    setExportError(null);
    setSuccessMessage(null);
    try {
      const changes = buildChanges();
      if (changes) {
        await api.put(`/api/tailor/cv-versions/${result.cv_version_id}/accept-changes`, {
          accepted_changes: changes.acceptedChanges,
          rejected_changes: changes.rejectedChanges,
        });
      }
      const { blob, filename } = await api.downloadFile(`/api/export/pdf/${result.cv_version_id}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "cv.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF download failed:", err);
      setExportError("PDF compilation failed. Try 'Save & Open in Overleaf' to download a PDF instead.");
    } finally {
      setSaving(false);
    }
  };

  // Count summary
  const counts = { accepted: 0, rejected: 0, edited: 0, total: 0 };
  for (const expDecisions of Object.values(decisions)) {
    for (const bullet of Object.values(expDecisions)) {
      counts.total++;
      if (bullet.decision === "accept") counts.accepted++;
      else if (bullet.decision === "reject") counts.rejected++;
      else if (bullet.decision === "edit") counts.edited++;
    }
  }

  const buildChanges = () => {
    if (!result) return null;
    const acceptedChanges: Record<string, string[]> = {};
    const rejectedChanges: Record<string, number[]> = {};

    for (const [expId, expDecisions] of Object.entries(decisions)) {
      const diff = result.diff_json[expId];
      if (!diff) continue;

      const acceptedBullets: string[] = [];
      const rejectedIndices: number[] = [];

      for (const [idxStr, bullet] of Object.entries(expDecisions)) {
        const idx = parseInt(idxStr);
        if (bullet.decision === "accept") {
          // Use edited text if user modified it, otherwise use suggested
          if (bullet.editedText) {
            acceptedBullets.push(bullet.editedText);
          } else {
            acceptedBullets.push(bulletText(diff.suggested_bullets[idx]));
          }
        } else if (bullet.decision === "edit" && bullet.editedText) {
          acceptedBullets.push(bullet.editedText);
        } else {
          acceptedBullets.push(diff.original_bullets[idx] || bulletText(diff.suggested_bullets[idx]));
          rejectedIndices.push(idx);
        }
      }

      acceptedChanges[expId] = acceptedBullets;
      if (rejectedIndices.length > 0) {
        rejectedChanges[expId] = rejectedIndices;
      }
    }

    // Apply manual edits to education achievements and modules
    if (result.education_data) {
      for (const edu of result.education_data) {
        const achievements: string[] = [];
        const modules: string[] = [];

        if (edu.achievements) {
          for (let i = 0; i < edu.achievements.length; i++) {
            const key = `achievement_${edu.id}_${i}`;
            achievements.push(manualEdits[key] || String(edu.achievements[i]));
          }
        }

        const modulesKey = `modules_${edu.id}`;
        if (manualEdits[modulesKey]) {
          modules.push(
            ...manualEdits[modulesKey]
              .split(",")
              .map((m) => m.trim())
              .filter((m) => m)
          );
        } else if (edu.achievements) {
          modules.push(...edu.achievements);
        }

        acceptedChanges[`education_${edu.id}`] = {
          achievements,
          modules,
        } as unknown as string[];
      }
    }

    // Apply manual edits to skills
    if (result.skills_data) {
      for (const [category, skills] of Object.entries(result.skills_data)) {
        const key = `skills_${category}`;
        // skills_data contains arrays, when edited by user it's comma-separated string
        // Convert back to array format for backend
        if (manualEdits[key]) {
          // User edited: convert comma-separated string to array
          const skillsArray = manualEdits[key].split(",").map((s) => s.trim()).filter((s) => s);
          acceptedChanges[`skills_${category}`] = skillsArray;
        } else {
          // Use original data as-is (already an array)
          acceptedChanges[`skills_${category}`] = skills;
        }
      }
    }

    return { acceptedChanges, rejectedChanges };
  };

  const handleOpenOverleaf = async () => {
    if (!result) return;
    setSaving(true);
    setExportError(null);
    setSuccessMessage(null);

    try {
      const changes = buildChanges();
      if (changes) {
        await api.put(`/api/tailor/cv-versions/${result.cv_version_id}/accept-changes`, {
          accepted_changes: changes.acceptedChanges,
          rejected_changes: changes.rejectedChanges,
        });
      }

      const data = await api.post<{ success: boolean; latex_content: string }>(`/api/export/overleaf/${result.cv_version_id}`);
      if (data.latex_content) {
        // Use a hidden POST form to send LaTeX to Overleaf (avoids URL length limits)
        const form = document.createElement("form");
        form.method = "POST";
        form.action = "https://www.overleaf.com/docs";
        form.target = "_blank";

        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "snip";
        input.value = data.latex_content;
        form.appendChild(input);

        const nameInput = document.createElement("input");
        nameInput.type = "hidden";
        nameInput.name = "snip_name";
        nameInput.value = "cv.tex";
        form.appendChild(nameInput);

        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
      } else {
        setExportError("Failed to generate Overleaf content.");
      }
    } catch (err) {
      console.error("Overleaf open failed:", err);
      setExportError("Failed to open Overleaf. Check console for details.");
    } finally {
      setSaving(false);
    }
  };

  const handleReTailor = () => {
    if (!result) return;
    setShowRetailorConfirm(true);
  };

  const confirmReTailor = async () => {
    setShowRetailorConfirm(false);
    setRetailoring(true);
    setExportError(null);
    setSuccessMessage(null);
    try {
      await api.post(`/api/tailor/re-tailor/${applicationId}`);
      await fetchResult();
      setSuccessMessage("Re-tailoring complete! Review the updated suggestions.");
    } catch (err) {
      console.error("Re-tailoring failed:", err);
      setExportError("Failed to re-tailor. Check console for details.");
    } finally {
      setRetailoring(false);
    }
  };

  const handleRegenerateBullet = async (expId: string, idx: number) => {
    setRegeneratingBullet({ expId, idx });
    setExportError(null);
    try {
      const data = await api.post<{ suggested_bullet: { text: string; has_placeholder: boolean; outcome_type: string } }>(
        "/api/tailor/regenerate-bullet",
        { application_id: applicationId, experience_id: expId, bullet_index: idx }
      );
      setResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          diff_json: {
            ...prev.diff_json,
            [expId]: {
              ...prev.diff_json[expId],
              suggested_bullets: prev.diff_json[expId].suggested_bullets.map((b, i) =>
                i === idx ? data.suggested_bullet : b
              ),
            },
          },
        };
      });
      setBulletDecision(expId, idx, "accept");
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Failed to regenerate bullet");
    } finally {
      setRegeneratingBullet(null);
    }
  };

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

  const experienceDiffs = sortByDateDesc(
    Object.entries(result.diff_json).filter(([, d]) => !d.type || d.type === "experience"),
    result
  );
  const projectDiffs = sortByDateDesc(
    Object.entries(result.diff_json).filter(([, d]) => d.type === "project"),
    result
  );
  const activityDiffs = sortByDateDesc(
    Object.entries(result.diff_json).filter(([, d]) => d.type === "activity"),
    result
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Review Tailored CV</h1>
        <div className="flex items-center gap-2">
          <div className="text-sm text-muted-foreground mr-2">
            {counts.total} suggestions &mdash; {counts.accepted} accepted,{" "}
            {counts.rejected} rejected, {counts.edited} edited
          </div>
          {recoveredFromStorage && (
            <div className="flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700">
              <span>Recovered unsaved edits</span>
              <button
                onClick={() => setRecoveredFromStorage(false)}
                className="text-blue-400 hover:text-blue-600"
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
          )}

          {/* Bulk decision shortcuts */}
          <button
            onClick={acceptAll}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            title="Accept all suggestions"
          >
            Accept All
          </button>
          <button
            onClick={rejectAll}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            title="Reject all suggestions"
          >
            Reject All
          </button>

          <div className="h-5 w-px bg-gray-200" />

          {/* Re-tailor — kept separate as it re-runs the pipeline */}
          <button
            onClick={handleReTailor}
            disabled={retailoring}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            title="Re-run tailoring with latest optimizations"
          >
            {retailoring ? "Re-tailoring..." : "Re-tailor"}
          </button>

          {/* Reset dropdown */}
          <div className="relative" ref={resetMenuRef}>
            <button
              onClick={() => setResetMenuOpen((o) => !o)}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 flex items-center gap-1"
            >
              Reset <span className="text-[10px] leading-none">▾</span>
            </button>
            {resetMenuOpen && (
              <div className="absolute right-0 top-full mt-1 z-20 w-44 rounded-md border border-gray-200 bg-white shadow-md py-1">
                <button
                  onClick={() => { resetAllDecisions(); setResetMenuOpen(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  Reset Decisions
                </button>
                <button
                  onClick={() => { resetAllEdits(); setResetMenuOpen(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  Reset Edits
                </button>
              </div>
            )}
          </div>

          {/* Export dropdown — primary CTA */}
          <div className="relative" ref={exportMenuRef}>
            <button
              onClick={() => setExportMenuOpen((o) => !o)}
              disabled={saving}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1.5"
            >
              {saving ? "Exporting..." : "Export"} <span className="text-[10px] leading-none">▾</span>
            </button>
            {exportMenuOpen && (
              <div className="absolute right-0 top-full mt-1 z-20 w-52 rounded-md border border-gray-200 bg-white shadow-md py-1">
                <button
                  onClick={() => { handleDownloadPdf(); setExportMenuOpen(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  Download PDF
                </button>
                <button
                  onClick={() => { handleOpenOverleaf(); setExportMenuOpen(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  Open in Overleaf ↗
                </button>
                <div className="my-1 border-t border-gray-100" />
                <button
                  onClick={() => { handleDownloadLatex(); setExportMenuOpen(false); }}
                  className="w-full px-4 py-2 text-left text-sm text-gray-500 hover:bg-gray-50"
                >
                  Download .tex
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ATS score panel */}
      {result.ats_score != null && (
        <AtsPanel score={result.ats_score} warnings={result.ats_warnings ?? []} />
      )}

      {/* Inline re-tailor confirmation */}
      {showRetailorConfirm && (
        <div className="flex items-center gap-4 rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          <span>Re-tailor this application? This will apply the latest tailoring logic.</span>
          <button
            onClick={confirmReTailor}
            className="rounded-md bg-yellow-600 px-3 py-1 text-xs font-medium text-white hover:bg-yellow-700"
          >
            Confirm
          </button>
          <button
            onClick={() => setShowRetailorConfirm(false)}
            className="rounded-md border border-yellow-400 px-3 py-1 text-xs font-medium hover:bg-yellow-100"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Inline success/error messages */}
      {successMessage && (
        <div className="flex items-center justify-between rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          <span>{successMessage}</span>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-green-400 hover:text-green-600"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}
      {exportError && (
        <div className="flex items-center justify-between rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{exportError}</span>
          <button
            onClick={() => setExportError(null)}
            className="text-red-400 hover:text-red-600"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      {/* View Mode Toggle */}
      <div className="flex gap-1 rounded-lg bg-muted p-1 w-fit">
        <button
          onClick={() => setViewMode("diff")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            viewMode === "diff"
              ? "bg-white text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Diff View
        </button>
        <button
          onClick={() => setViewMode("preview")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            viewMode === "preview"
              ? "bg-white text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
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
          setManualEdit={handleSetManualEdit}
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
          setManualEdit={handleSetManualEdit}
          regeneratingBullet={regeneratingBullet}
          onRegenerateBullet={handleRegenerateBullet}
        />
      )}

    </div>
  );
}
