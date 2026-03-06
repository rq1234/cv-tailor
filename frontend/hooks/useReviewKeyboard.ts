"use client";

import { useEffect } from "react";
import type { BulletState, ExperienceDiff } from "@/components/review/types";

export interface FlatBullet {
  expId: string;
  idx: number;
}

/** Build a flat ordered list of bullets from the three diff sections. */
export function buildFlatBullets(
  experienceDiffs: [string, ExperienceDiff][],
  projectDiffs: [string, ExperienceDiff][],
  activityDiffs: [string, ExperienceDiff][],
): FlatBullet[] {
  const flat: FlatBullet[] = [];
  for (const [expId, diff] of [...experienceDiffs, ...projectDiffs, ...activityDiffs]) {
    for (let i = 0; i < diff.suggested_bullets.length; i++) {
      flat.push({ expId, idx: i });
    }
  }
  return flat;
}

interface UseReviewKeyboardOptions {
  flatBullets: FlatBullet[];
  focusedIdx: number | null;
  setFocusedIdx: (idx: number | null) => void;
  setBulletDecision: (expId: string, idx: number, decision: "accept" | "reject" | "edit", editedText?: string) => void;
  decisions: Record<string, Record<number, BulletState>>;
}

/**
 * Keyboard shortcuts for the review page:
 *   Tab / ArrowDown   → next bullet
 *   Shift+Tab / ArrowUp → prev bullet
 *   A                 → accept focused bullet
 *   R                 → reject focused bullet
 *   E                 → edit focused bullet (opens inline edit)
 *   Escape            → clear focus
 *
 * Only fires when no input/textarea is focused.
 */
export function useReviewKeyboard({
  flatBullets,
  focusedIdx,
  setFocusedIdx,
  setBulletDecision,
  decisions,
}: UseReviewKeyboardOptions): void {
  useEffect(() => {
    if (flatBullets.length === 0) return;

    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;

      const current = focusedIdx ?? -1;

      if (e.key === "Tab" || e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const goBack = e.key === "ArrowUp" || (e.key === "Tab" && e.shiftKey);
        const next = goBack
          ? Math.max(0, current - 1)
          : Math.min(flatBullets.length - 1, current + 1);
        setFocusedIdx(next);
        scrollBulletIntoView(flatBullets[next]);
        return;
      }
      if (e.key === "Escape") {
        setFocusedIdx(null);
        return;
      }

      // A/R/E only when a bullet is focused
      if (focusedIdx === null || focusedIdx < 0 || focusedIdx >= flatBullets.length) return;
      const { expId, idx } = flatBullets[focusedIdx];
      const currentDecision = decisions[expId]?.[idx]?.decision ?? "pending";

      if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        setBulletDecision(expId, idx, "accept", decisions[expId]?.[idx]?.editedText);
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        setBulletDecision(expId, idx, "reject", decisions[expId]?.[idx]?.editedText);
      } else if (e.key === "e" || e.key === "E") {
        e.preventDefault();
        if (currentDecision !== "edit") {
          setBulletDecision(expId, idx, "edit", decisions[expId]?.[idx]?.editedText ?? "");
        }
        // Focus the textarea for this bullet
        setTimeout(() => {
          const el = document.querySelector<HTMLTextAreaElement>(
            `[data-bullet-id="${expId}-${idx}"] textarea`
          );
          el?.focus();
        }, 50);
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [flatBullets, focusedIdx, setFocusedIdx, setBulletDecision, decisions]);
}

function scrollBulletIntoView({ expId, idx }: FlatBullet) {
  const el = document.querySelector(`[data-bullet-id="${expId}-${idx}"]`);
  el?.scrollIntoView({ block: "center", behavior: "smooth" });
}
