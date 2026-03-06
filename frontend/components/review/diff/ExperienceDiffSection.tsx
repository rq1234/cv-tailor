import { useState } from "react";
import {
  type BulletState,
  type ExperienceDiff,
  type TailorResult,
  getDiffMeta,
} from "../types";
import { BulletDiffCard } from "./BulletDiffCard";

function getBulletSummary(
  entryDecisions: Record<number, BulletState> | undefined,
  total: number
): string {
  if (!entryDecisions) return `${total} bullet${total !== 1 ? "s" : ""}`;
  const vals = Object.values(entryDecisions);
  const a = vals.filter((b) => b.decision === "accept").length;
  const r = vals.filter((b) => b.decision === "reject").length;
  const e = vals.filter((b) => b.decision === "edit").length;
  const pending = total - a - r - e;
  const parts = [`${total} bullets`];
  if (a > 0) parts.push(`${a} ✓`);
  if (r > 0) parts.push(`${r} ✗`);
  if (e > 0) parts.push(`${e} edited`);
  if (pending > 0) parts.push(`${pending} pending`);
  return parts.join(" · ");
}

interface ExperienceDiffSectionProps {
  label: string;
  entries: [string, ExperienceDiff][];
  result: TailorResult;
  decisions: Record<string, Record<number, BulletState>>;
  setBulletDecision: (expId: string, idx: number, decision: "accept" | "reject" | "edit", editedText?: string) => void;
  regeneratingBullet?: { expId: string; idx: number } | null;
  onRegenerateBullet?: (expId: string, idx: number, hint?: string) => void;
  focusedBullet?: { expId: string; idx: number } | null;
}

export function ExperienceDiffSection({
  label,
  entries,
  result,
  decisions,
  setBulletDecision,
  regeneratingBullet,
  onRegenerateBullet,
  focusedBullet = null,
}: ExperienceDiffSectionProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const sectionIds = entries.map(([id]) => id);
  const allCollapsed = sectionIds.length > 0 && sectionIds.every((id) => collapsed.has(id));

  const toggleCollapsed = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const collapseAll = () => setCollapsed(new Set(sectionIds));
  const expandAll = () => setCollapsed(new Set());

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-bold">{label}</h2>
        <div className="flex items-center gap-3">
          <button
            onClick={() =>
              entries.forEach(([entryId, diff]) => {
                for (let i = 0; i < diff.suggested_bullets.length; i++)
                  setBulletDecision(entryId, i, "accept");
              })
            }
            className="text-xs text-emerald-600 hover:text-emerald-700 underline"
          >
            Accept all
          </button>
          <button
            onClick={() =>
              entries.forEach(([entryId, diff]) => {
                for (let i = 0; i < diff.suggested_bullets.length; i++)
                  setBulletDecision(entryId, i, "reject");
              })
            }
            className="text-xs text-red-500 hover:text-red-600 underline"
          >
            Reject all
          </button>
          <button
            onClick={() => (allCollapsed ? expandAll() : collapseAll())}
            className="text-xs text-muted-foreground hover:text-foreground underline"
          >
            {allCollapsed ? "Expand all" : "Collapse all"}
          </button>
        </div>
      </div>

      {entries.map(([entryId, diff]) => {
        const meta = getDiffMeta(entryId, diff, result);
        const borderColour =
          diff.confidence >= 0.85
            ? "border-green-200"
            : diff.confidence < 0.7
            ? "border-amber-200"
            : "border-gray-200";
        const isCollapsed = collapsed.has(entryId);

        return (
          <div key={entryId} className={`rounded-lg border mb-4 ${borderColour}`}>
            {/* Card header */}
            <div
              className="border-b bg-muted/50 px-4 py-3 cursor-pointer select-none"
              onClick={() => toggleCollapsed(entryId)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="flex-shrink-0 text-muted-foreground text-xs">
                    {isCollapsed ? "▸" : "▾"}
                  </span>
                  <div className="min-w-0">
                    <span className="text-sm font-semibold">{meta.title}</span>
                    {meta.subtitle && (
                      <span className="text-sm text-muted-foreground">
                        {" "}
                        {meta.isProject ? "" : "at "}
                        {meta.subtitle}
                      </span>
                    )}
                    {meta.dateRange && (
                      <span className="ml-2 text-xs text-muted-foreground">({meta.dateRange})</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0 ml-2">
                  {isCollapsed && (
                    <span className="text-xs text-muted-foreground">
                      {getBulletSummary(decisions[entryId], diff.suggested_bullets.length)}
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {(diff.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
              {!isCollapsed && diff.coaching_note && (
                <p className="mt-1.5 text-xs text-muted-foreground italic">
                  💡 {diff.coaching_note}
                </p>
              )}
              {!isCollapsed && diff.changes_made.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {diff.changes_made.map((change, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                    >
                      {change}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Bullet list */}
            {!isCollapsed && (
              <div className="divide-y">
                {diff.suggested_bullets.map((suggested, idx) => (
                  <BulletDiffCard
                    key={idx}
                    entryId={entryId}
                    idx={idx}
                    original={diff.original_bullets[idx] || ""}
                    suggested={suggested}
                    bulletState={decisions[entryId]?.[idx]}
                    setBulletDecision={setBulletDecision}
                    regeneratingBullet={regeneratingBullet}
                    onRegenerateBullet={onRegenerateBullet}
                    isFocused={focusedBullet?.expId === entryId && focusedBullet?.idx === idx}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
