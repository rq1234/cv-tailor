import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
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
  const [rejectConfirm, setRejectConfirm] = useState(false);

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

  const handleAcceptAll = () => {
    entries.forEach(([entryId, diff]) => {
      for (let i = 0; i < diff.suggested_bullets.length; i++)
        setBulletDecision(entryId, i, "accept");
    });
  };

  const handleRejectAll = () => {
    if (!rejectConfirm) {
      setRejectConfirm(true);
      return;
    }
    entries.forEach(([entryId, diff]) => {
      for (let i = 0; i < diff.suggested_bullets.length; i++)
        setBulletDecision(entryId, i, "reject");
    });
    setRejectConfirm(false);
  };

  useEffect(() => {
    if (!rejectConfirm) return;
    const t = setTimeout(() => setRejectConfirm(false), 3000);
    return () => clearTimeout(t);
  }, [rejectConfirm]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="text-lg font-bold">{label}</h2>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleAcceptAll}
            className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
          >
            <Check className="h-3 w-3" /> Accept all
          </button>
          <button
            onClick={handleRejectAll}
            className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium transition-colors ${
              rejectConfirm
                ? "border-red-300 bg-red-100 text-red-700 hover:bg-red-200"
                : "border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
            }`}
          >
            <X className="h-3 w-3" /> {rejectConfirm ? "Confirm?" : "Reject all"}
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
        const isCollapsed = collapsed.has(entryId);

        return (
          <div
          key={entryId}
          className={`rounded-lg border mb-4 border-l-4 ${
            diff.confidence >= 0.75
              ? "border-l-emerald-400"
              : diff.confidence >= 0.5
              ? "border-l-amber-400"
              : "border-l-red-400"
          } border-gray-200`}
        >
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
                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                  <span
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                      diff.confidence >= 0.75
                        ? "bg-emerald-100 text-emerald-700"
                        : diff.confidence >= 0.5
                        ? "bg-amber-100 text-amber-700"
                        : "bg-red-100 text-red-600"
                    }`}
                    title={`AI confidence: ${Math.round(diff.confidence * 100)}%`}
                  >
                    {Math.round(diff.confidence * 100)}%
                  </span>
                  {isCollapsed && (
                    <span className="text-xs text-muted-foreground">
                      {getBulletSummary(decisions[entryId], diff.suggested_bullets.length)}
                    </span>
                  )}
                </div>
              </div>
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
