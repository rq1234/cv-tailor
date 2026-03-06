"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  type ExperienceDiff,
  type TailorResult,
  bulletText,
  sortByDateDesc,
} from "@/components/review/types";
import { useReviewDecisions } from "./useReviewDecisions";
import { useReviewExports } from "./useReviewExports";

interface Counts {
  accepted: number;
  rejected: number;
  edited: number;
  pending: number;
  total: number;
}

export function useReviewPage(applicationId: string) {
  const [result, setResult] = useState<TailorResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retailoring, setRetailoring] = useState(false);
  const [showRetailorConfirm, setShowRetailorConfirm] = useState(false);
  const [regeneratingBullet, setRegeneratingBullet] = useState<{ expId: string; idx: number } | null>(null);

  const decisionState = useReviewDecisions(applicationId, result);
  const { decisions, manualEdits, rejectedVariants, setRejectedVariants, setBulletDecision } = decisionState;

  const exportState = useReviewExports(result, decisions, manualEdits);
  const { setExportError, setSuccessMessage } = exportState;

  const fetchResult = useCallback(async () => {
    try {
      const data = await api.get<TailorResult>(`/api/tailor/result/${applicationId}`);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load result");
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    fetchResult();
  }, [fetchResult]);

  // ── Re-tailor ─────────────────────────────────────────────────────────────
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
  }, [applicationId, fetchResult, setExportError, setSuccessMessage]);

  // ── Bullet regeneration ───────────────────────────────────────────────────
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
  }, [applicationId, result, rejectedVariants, setBulletDecision, setExportError, setRejectedVariants]);

  // ── Computed values ───────────────────────────────────────────────────────
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
    retailoring,
    showRetailorConfirm,
    regeneratingBullet,
    counts,
    experienceDiffs,
    projectDiffs,
    activityDiffs,
    // from useReviewDecisions
    ...decisionState,
    // from useReviewExports
    ...exportState,
    // re-tailor
    handleReTailor,
    confirmReTailor,
    cancelReTailor,
    // bullet regen
    handleRegenerateBullet,
  };
}
