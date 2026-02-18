"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import DiffView from "@/components/review/DiffView";
import PreviewView from "@/components/review/PreviewView";
import {
  type BulletDecision,
  type BulletState,
  type TailorResult,
  bulletText,
  sortByDateDesc,
} from "@/components/review/types";

export default function ReviewPage() {
  const params = useParams();
  const applicationId = params.applicationId as string;
  const [result, setResult] = useState<TailorResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [retailoring, setRetailoring] = useState(false);
  const [viewMode, setViewMode] = useState<"diff" | "preview">("diff");
  const [decisions, setDecisions] = useState<Record<string, Record<number, BulletState>>>({});
  const [manualEdits, setManualEdits] = useState<Record<string, string>>({});
  const [recoveredFromStorage, setRecoveredFromStorage] = useState(false);

  // localStorage key unique to this application
  const storageKey = `cv-edits-${applicationId}`;

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

  // Auto-save to localStorage whenever decisions or edits change
  useEffect(() => {
    if (decisions && Object.keys(decisions).length > 0) {
      try {
        const toStore = { decisions, manualEdits };
        localStorage.setItem(storageKey, JSON.stringify(toStore));
      } catch (e) {
        console.warn("Failed to save to localStorage:", e);
      }
    }
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

    try {
      const changes = buildChanges();
      if (changes) {
        await api.put(`/api/tailor/cv-versions/${result.cv_version_id}/accept-changes`, {
          accepted_changes: changes.acceptedChanges,
          rejected_changes: changes.rejectedChanges,
        });
      }

      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/api/export/overleaf/${result.cv_version_id}`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to generate Overleaf link");
      }

      const data = await response.json();
      if (data.latex_content) {
        // Use a hidden POST form to send LaTeX to Overleaf (avoids URL length limits)
        const form = document.createElement("form");
        form.method = "POST";
        form.action = "https://www.overleaf.com/docs";
        form.target = "_blank";

        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "snip_uri";
        // Encode as a data URI so Overleaf can read it
        const encoded = btoa(unescape(encodeURIComponent(data.latex_content)));
        input.value = `data:application/x-tex;base64,${encoded}`;
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
        alert("Failed to generate Overleaf content");
      }
    } catch (err) {
      console.error("Overleaf open failed:", err);
      alert("Failed to open Overleaf. Check console for details.");
    } finally {
      setSaving(false);
    }
  };

  const handleReTailor = async () => {
    if (!result) return;
    
    const confirmed = window.confirm(
      "Re-tailor this application? This will apply the latest tailoring logic and reset your accept/reject decisions."
    );
    
    if (!confirmed) return;
    
    setRetailoring(true);
    
    try {
      await api.post(`/api/tailor/re-tailor/${applicationId}`);
      // Refresh the result
      await fetchResult();
      alert("Re-tailoring complete! Review the updated suggestions.");
    } catch (err) {
      console.error("Re-tailoring failed:", err);
      alert("Failed to re-tailor. Check console for details.");
    } finally {
      setRetailoring(false);
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
        <div className="flex items-center gap-4">
          <div className="text-sm text-muted-foreground">
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
          <button
            onClick={handleReTailor}
            disabled={retailoring}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            title="Re-run tailoring with latest optimizations (keeps your decisions)"
          >
            {retailoring ? "Re-tailoring..." : "Re-tailor"}
          </button>
          <button
            onClick={() => resetAllEdits()}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            title="Reset all manual edits to original"
          >
            Reset Edits
          </button>
          <button
            onClick={() => resetAllDecisions()}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            title="Reset all accept/reject/edit decisions"
          >
            Reset Decisions
          </button>
          <button
            onClick={handleOpenOverleaf}
            disabled={saving}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save & Open in Overleaf"}
          </button>
        </div>
      </div>

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
        />
      )}

    </div>
  );
}
