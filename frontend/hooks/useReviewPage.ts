"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import {
  type BulletDecision,
  type BulletState,
  type ExperienceDiff,
  type TailorResult,
  bulletText,
  sortByDateDesc,
} from "@/components/review/types";

interface Counts {
  accepted: number;
  rejected: number;
  edited: number;
  pending: number;
  total: number;
}

interface AcceptChangesPayload {
  acceptedChanges: Record<string, string[] | unknown>;
  rejectedChanges: Record<string, number[]>;
}

function buildChanges(
  result: TailorResult,
  decisions: Record<string, Record<number, BulletState>>,
  manualEdits: Record<string, string>
): AcceptChangesPayload {
  const acceptedChanges: Record<string, string[] | unknown> = {};
  const rejectedChanges: Record<string, number[]> = {};

  for (const [expId, expDecisions] of Object.entries(decisions)) {
    const diff = result.diff_json[expId];
    if (!diff) continue;

    const acceptedBullets: string[] = [];
    const rejectedIndices: number[] = [];

    for (const [idxStr, bullet] of Object.entries(expDecisions)) {
      const idx = parseInt(idxStr);
      if (bullet.decision === "accept" || bullet.decision === "pending") {
        acceptedBullets.push(bullet.editedText ?? bulletText(diff.suggested_bullets[idx]));
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

  // Manual edits for education
  if (result.education_data) {
    for (const edu of result.education_data) {
      const achievements: string[] = [];
      if (edu.achievements) {
        for (let i = 0; i < edu.achievements.length; i++) {
          achievements.push(manualEdits[`achievement_${edu.id}_${i}`] || String(edu.achievements[i]));
        }
      }
      const modulesKey = `modules_${edu.id}`;
      const modules = manualEdits[modulesKey]
        ? manualEdits[modulesKey].split(",").map((m) => m.trim()).filter(Boolean)
        : edu.modules ?? [];
      acceptedChanges[`education_${edu.id}`] = { achievements, modules } as unknown;
    }
  }

  // Manual edits for skills
  if (result.skills_data) {
    for (const [category, skills] of Object.entries(result.skills_data)) {
      const key = `skills_${category}`;
      acceptedChanges[`skills_${category}`] = manualEdits[key]
        ? manualEdits[key].split(",").map((s) => s.trim()).filter(Boolean)
        : skills;
    }
  }

  return { acceptedChanges, rejectedChanges };
}

async function saveChanges(
  result: TailorResult,
  decisions: Record<string, Record<number, BulletState>>,
  manualEdits: Record<string, string>
) {
  const changes = buildChanges(result, decisions, manualEdits);
  await api.put(`/api/tailor/cv-versions/${result.cv_version_id}/accept-changes`, {
    accepted_changes: changes.acceptedChanges,
    rejected_changes: changes.rejectedChanges,
  });
}

export function useReviewPage(applicationId: string) {
  const [result, setResult] = useState<TailorResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [retailoring, setRetailoring] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showRetailorConfirm, setShowRetailorConfirm] = useState(false);
  const [regeneratingBullet, setRegeneratingBullet] = useState<{ expId: string; idx: number } | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Record<number, BulletState>>>({});
  const [manualEdits, setManualEdits] = useState<Record<string, string>>({});
  const [recoveredFromStorage, setRecoveredFromStorage] = useState(false);
  const [rejectedVariants, setRejectedVariants] = useState<Record<string, Record<number, string[]>>>({});
  const [storageWarning, setStorageWarning] = useState(false);

  const storageKey = `cv-edits-${applicationId}`;
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const makeInitialDecisions = (data: TailorResult) => {
    const initial: Record<string, Record<number, BulletState>> = {};
    for (const [expId, diff] of Object.entries(data.diff_json || {})) {
      initial[expId] = {};
      // Auto-accept high-confidence entries; mark low-confidence as pending for review
      const autoAccept = diff.confidence >= 0.75;
      for (let i = 0; i < diff.suggested_bullets.length; i++) {
        initial[expId][i] = { decision: autoAccept ? "accept" : "pending" };
      }
    }
    return initial;
  };

  const fetchResult = useCallback(async () => {
    try {
      const data = await api.get<TailorResult>(`/api/tailor/result/${applicationId}`);
      setResult(data);
      const initial = makeInitialDecisions(data);

      try {
        const stored = localStorage.getItem(storageKey);
        if (stored) {
          const { decisions: storedDecisions, manualEdits: storedEdits } = JSON.parse(stored);
          setDecisions({ ...initial, ...storedDecisions });
          setManualEdits(storedEdits || {});
          setRecoveredFromStorage(true);
        } else {
          setDecisions(initial);
        }
      } catch {
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

  // Debounced localStorage auto-save
  useEffect(() => {
    if (!decisions || Object.keys(decisions).length === 0) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(storageKey, JSON.stringify({ decisions, manualEdits }));
        setStorageWarning(false);
      } catch {
        setStorageWarning(true);
      }
    }, 300);
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
  }, [decisions, manualEdits, storageKey]);

  // ── Decision helpers ────────────────────────────────────────────────
  const setBulletDecision = useCallback((
    expId: string, bulletIndex: number, decision: BulletDecision, editedText?: string
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
  }, []);

  const setManualEdit = useCallback((key: string, value: string) => {
    setManualEdits((prev) => ({ ...prev, [key]: value }));
  }, []);

  const acceptAll = useCallback(() => {
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
  }, []);

  const rejectAll = useCallback(() => {
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
  }, []);

  const resetAllDecisions = useCallback(() => {
    if (!result) return;
    setDecisions(makeInitialDecisions(result));
  }, [result]);

  const resetAllEdits = useCallback(() => setManualEdits({}), []);

  // ── Export handlers ─────────────────────────────────────────────────
  const handleDownloadPdf = useCallback(async () => {
    if (!result) return;
    setSaving(true);
    setExportError(null);
    setSuccessMessage(null);
    try {
      await saveChanges(result, decisions, manualEdits);
      const { blob, filename } = await api.downloadFile(`/api/export/pdf/${result.cv_version_id}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename || "cv.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch {
      setExportError("PDF compilation failed. Try 'Open in Overleaf' instead.");
    } finally {
      setSaving(false);
    }
  }, [result, decisions, manualEdits]);

  const handleDownloadLatex = useCallback(async () => {
    if (!result) return;
    setSaving(true);
    setExportError(null);
    setSuccessMessage(null);
    try {
      await saveChanges(result, decisions, manualEdits);
      const { blob, filename } = await api.downloadFile(`/api/export/latex/${result.cv_version_id}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename || "cv.tex"; a.click();
      URL.revokeObjectURL(url);
    } catch {
      setExportError("Failed to download LaTeX file.");
    } finally {
      setSaving(false);
    }
  }, [result, decisions, manualEdits]);

  const handleDownloadDocx = useCallback(async () => {
    if (!result) return;
    setSaving(true);
    setExportError(null);
    setSuccessMessage(null);
    try {
      await saveChanges(result, decisions, manualEdits);
      const { blob, filename } = await api.downloadFilePost(`/api/export/docx/${result.cv_version_id}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename || "cv.docx"; a.click();
      URL.revokeObjectURL(url);
    } catch {
      setExportError("DOCX generation failed. Try downloading the PDF instead.");
    } finally {
      setSaving(false);
    }
  }, [result, decisions, manualEdits]);

  const handleOpenOverleaf = useCallback(async () => {
    if (!result) return;
    setSaving(true);
    setExportError(null);
    setSuccessMessage(null);
    try {
      await saveChanges(result, decisions, manualEdits);
      const data = await api.post<{ success: boolean; latex_content: string }>(
        `/api/export/overleaf/${result.cv_version_id}`
      );
      if (data.latex_content) {
        const form = document.createElement("form");
        form.method = "POST";
        form.action = "https://www.overleaf.com/docs";
        form.target = "_blank";
        const snip = document.createElement("input");
        snip.type = "hidden"; snip.name = "snip"; snip.value = data.latex_content;
        const name = document.createElement("input");
        name.type = "hidden"; name.name = "snip_name"; name.value = "cv.tex";
        form.append(snip, name);
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
      } else {
        setExportError("Failed to generate Overleaf content.");
      }
    } catch {
      setExportError("Failed to open Overleaf.");
    } finally {
      setSaving(false);
    }
  }, [result, decisions, manualEdits]);

  // ── Re-tailor ───────────────────────────────────────────────────────
  const handleReTailor = useCallback(() => setShowRetailorConfirm(true), []);
  const cancelReTailor = useCallback(() => setShowRetailorConfirm(false), []);

  const confirmReTailor = useCallback(async () => {
    setShowRetailorConfirm(false);
    setRetailoring(true);
    setExportError(null);
    setSuccessMessage(null);
    try {
      await api.post(`/api/tailor/re-tailor/${applicationId}`);
      await fetchResult();
      setSuccessMessage("Re-tailoring complete! Review the updated suggestions.");
    } catch {
      setExportError("Failed to re-tailor.");
    } finally {
      setRetailoring(false);
    }
  }, [applicationId, fetchResult]);

  // ── Bullet regeneration ─────────────────────────────────────────────
  const handleRegenerateBullet = useCallback(async (expId: string, idx: number, hint?: string) => {
    setRegeneratingBullet({ expId, idx });
    setExportError(null);
    try {
      if (result?.diff_json[expId]?.suggested_bullets[idx]) {
        const current = bulletText(result.diff_json[expId].suggested_bullets[idx]);
        setRejectedVariants((prev) => ({
          ...prev,
          [expId]: { ...prev[expId], [idx]: [...(prev[expId]?.[idx] ?? []), current] },
        }));
      }
      const data = await api.post<{ suggested_bullet: ExperienceDiff["suggested_bullets"][number] }>(
        "/api/tailor/regenerate-bullet",
        {
          application_id: applicationId,
          experience_id: expId,
          bullet_index: idx,
          hint: hint || null,
          rejected_variants: rejectedVariants[expId]?.[idx] ?? null,
        }
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
  }, [applicationId, result, rejectedVariants, setBulletDecision]);

  // ── Computed values ─────────────────────────────────────────────────
  const counts: Counts = { accepted: 0, rejected: 0, edited: 0, pending: 0, total: 0 };
  for (const expDecisions of Object.values(decisions)) {
    for (const bullet of Object.values(expDecisions)) {
      counts.total++;
      if (bullet.decision === "accept") counts.accepted++;
      else if (bullet.decision === "reject") counts.rejected++;
      else if (bullet.decision === "edit") counts.edited++;
      else if (bullet.decision === "pending") counts.pending++;
    }
  }

  const experienceDiffs = result
    ? sortByDateDesc(
        Object.entries(result.diff_json).filter(([, d]) => !d.type || d.type === "experience"),
        result
      )
    : [];
  const projectDiffs = result
    ? sortByDateDesc(
        Object.entries(result.diff_json).filter(([, d]) => d.type === "project"),
        result
      )
    : [];
  const activityDiffs = result
    ? sortByDateDesc(
        Object.entries(result.diff_json).filter(([, d]) => d.type === "activity"),
        result
      )
    : [];

  return {
    result,
    loading,
    error,
    decisions,
    manualEdits,
    rejectedVariants,
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
    dismissRecovered: () => setRecoveredFromStorage(false),
    clearExportError: () => setExportError(null),
    clearSuccessMessage: () => setSuccessMessage(null),
  };
}
