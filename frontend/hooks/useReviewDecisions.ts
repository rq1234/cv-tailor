"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type BulletDecision, type BulletState, type ExperienceDiff, type TailorResult } from "@/components/review/types";

function makeInitialDecisions(data: TailorResult): Record<string, Record<number, BulletState>> {
  const initial: Record<string, Record<number, BulletState>> = {};
  for (const [expId, diff] of Object.entries(data.diff_json || {})) {
    initial[expId] = {};
    const autoAccept = diff.confidence >= 0.75;
    for (let i = 0; i < diff.suggested_bullets.length; i++) {
      initial[expId][i] = { decision: autoAccept ? "accept" : "pending" };
    }
  }
  return initial;
}

export function useReviewDecisions(applicationId: string, result: TailorResult | null) {
  const storageKey = `cv-edits-${applicationId}`;
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [decisions, setDecisions] = useState<Record<string, Record<number, BulletState>>>({});
  const [manualEdits, setManualEditsState] = useState<Record<string, string>>({});
  const [rejectedVariants, setRejectedVariants] = useState<Record<string, Record<number, string[]>>>({});
  const [recoveredFromStorage, setRecoveredFromStorage] = useState(false);
  const [storageWarning, setStorageWarning] = useState(false);

  // Initialize decisions whenever a new result arrives; try to restore from localStorage.
  useEffect(() => {
    if (!result) return;
    const initial = makeInitialDecisions(result);
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const { decisions: storedDecisions, manualEdits: storedEdits } = JSON.parse(stored);
        // Only restore decisions for exp IDs and bullet indices that exist in the
        // current result — prevents stale indices carrying over after re-tailoring.
        const filtered: typeof initial = {};
        for (const [expId, expDecs] of Object.entries(storedDecisions || {})) {
          if (!(expId in initial)) continue;
          filtered[expId] = {};
          for (const [idxStr, state] of Object.entries(expDecs as Record<string, BulletState>)) {
            const idx = Number(idxStr);
            if (idx in initial[expId]) {
              filtered[expId][idx] = state as BulletState;
            }
          }
        }
        setDecisions({ ...initial, ...filtered });
        setManualEditsState(storedEdits || {});
        setRecoveredFromStorage(true);
        return;
      }
    } catch {
      // fall through to fresh init
    }
    setDecisions(initial);
  }, [result, storageKey]);

  // Debounced localStorage auto-save
  useEffect(() => {
    if (!decisions || Object.keys(decisions).length === 0) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(storageKey, JSON.stringify({ decisions, manualEdits: manualEdits }));
        setStorageWarning(false);
      } catch {
        setStorageWarning(true);
      }
    }, 300);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [decisions, manualEdits, storageKey]);

  const setBulletDecision = useCallback((
    expId: string, bulletIndex: number, decision: BulletDecision, editedText?: string
  ) => {
    setDecisions((prev) => {
      const preserved = editedText !== undefined ? editedText : prev[expId]?.[bulletIndex]?.editedText;
      const newState: BulletState = decision === "edit"
        ? { decision: "edit", editedText: preserved ?? "" }
        : { decision, editedText: preserved };
      return {
        ...prev,
        [expId]: { ...prev[expId], [bulletIndex]: newState },
      };
    });
  }, []);

  const setManualEdit = useCallback((key: string, value: string) => {
    setManualEditsState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetAllDecisions = useCallback(() => {
    if (!result) return;
    setDecisions(makeInitialDecisions(result));
  }, [result]);

  const resetAllEdits = useCallback(() => setManualEditsState({}), []);

  /**
   * Accept all pending bullets in entries where confidence >= threshold.
   * Already-decided bullets (accepted/rejected/edited) are left untouched.
   */
  const smartAccept = useCallback((
    threshold: number,
    diffJson: Record<string, ExperienceDiff>,
  ) => {
    setDecisions((prev) => {
      const next = { ...prev };
      for (const [expId, diff] of Object.entries(diffJson)) {
        if (diff.confidence < threshold) continue;
        const entryDecs = { ...(next[expId] ?? {}) };
        for (let i = 0; i < diff.suggested_bullets.length; i++) {
          const current = entryDecs[i];
          if (!current || current.decision === "pending") {
            entryDecs[i] = { decision: "accept" };
          }
        }
        next[expId] = entryDecs;
      }
      return next;
    });
  }, []);

  return {
    decisions,
    manualEdits,
    rejectedVariants,
    setRejectedVariants,
    recoveredFromStorage,
    storageWarning,
    setBulletDecision,
    setManualEdit,
    resetAllDecisions,
    resetAllEdits,
    smartAccept,
    dismissRecovered: () => setRecoveredFromStorage(false),
  };
}
