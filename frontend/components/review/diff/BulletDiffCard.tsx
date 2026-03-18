import { useRef, useState } from "react";
import { Check, X, Pencil, RefreshCw } from "lucide-react";
import {
  type BulletState,
  type ExperienceDiff,
  bulletHasPlaceholder,
  bulletText,
} from "../types";

// Matches: 50%, $3.2B, £1.4m, 1,400, 500k, 3.2x, numbers like 1400
const METRIC_RE = /(\$|£|€)?\d+(?:,\d+)*\.?\d*(%|[xX]|[kKmMbBtT]n?)?(?:\+)?/g;

function extractMetrics(text: string): string[] {
  return Array.from(new Set(text.match(METRIC_RE) ?? []));
}

function droppedMetrics(original: string, suggested: string): string[] {
  const inOriginal = extractMetrics(original);
  const sugLower = suggested.toLowerCase();
  return inOriginal.filter((m) => !sugLower.includes(m.toLowerCase()));
}

function HighlightedText({ text }: { text: string }) {
  const parts: { str: string; highlight: boolean }[] = [];
  let last = 0;
  for (const m of text.matchAll(METRIC_RE)) {
    if (m.index! > last) parts.push({ str: text.slice(last, m.index), highlight: false });
    parts.push({ str: m[0], highlight: true });
    last = m.index! + m[0].length;
  }
  if (last < text.length) parts.push({ str: text.slice(last), highlight: false });
  return (
    <>
      {parts.map((p, i) =>
        p.highlight ? (
          <mark key={i} className="bg-amber-100 text-amber-900 rounded px-0.5 font-medium not-italic">
            {p.str}
          </mark>
        ) : (
          <span key={i}>{p.str}</span>
        )
      )}
    </>
  );
}

interface BulletDiffCardProps {
  entryId: string;
  idx: number;
  original: string;
  suggested: ExperienceDiff["suggested_bullets"][number];
  bulletState: BulletState | undefined;
  setBulletDecision: (expId: string, idx: number, decision: "accept" | "reject" | "edit", editedText?: string) => void;
  regeneratingBullet?: { expId: string; idx: number } | null;
  onRegenerateBullet?: (expId: string, idx: number, hint?: string) => void;
  isFocused?: boolean;
}

export function BulletDiffCard({
  entryId,
  idx,
  original,
  suggested,
  bulletState,
  setBulletDecision,
  regeneratingBullet,
  onRegenerateBullet,
  isFocused = false,
}: BulletDiffCardProps) {
  const [hintInput, setHintInput] = useState("");
  const [swipeFlash, setSwipeFlash] = useState<"accept" | "reject" | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const touchStartX = useRef<number | null>(null);

  const text = bulletText(suggested);
  const hasPlaceholder = bulletHasPlaceholder(suggested);
  const isEditing = bulletState?.decision === "edit";
  const isReverted = bulletState?.decision === "reject";
  const isAccepted = bulletState?.decision === "accept";
  const isUnchanged = original.trim() === text.trim();
  const displayText = bulletState?.editedText ? bulletState.editedText : text;
  const dropped = droppedMetrics(original, text);
  const isRegenerating = regeneratingBullet?.expId === entryId && regeneratingBullet?.idx === idx;

  const SWIPE_THRESHOLD = 80;
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current === null) return;
    const delta = e.changedTouches[0].clientX - touchStartX.current;
    touchStartX.current = null;
    if (Math.abs(delta) < SWIPE_THRESHOLD) return;
    const direction = delta > 0 ? "accept" : "reject";
    setBulletDecision(entryId, idx, direction, bulletState?.editedText);
    setSwipeFlash(direction);
    setTimeout(() => setSwipeFlash(null), 400);
  };

  const flashBorder =
    swipeFlash === "accept" ? "ring-2 ring-inset ring-emerald-300"
    : swipeFlash === "reject" ? "ring-2 ring-inset ring-red-300"
    : "";

  const handleRegenerate = () => {
    if (!onRegenerateBullet) return;
    onRegenerateBullet(entryId, idx, hintInput.trim() || undefined);
    setHintInput("");
  };

  // Three-button group: Accept / Reject / Edit
  const actionButtons = (
    <div className="flex items-center gap-0.5">
      <button
        onClick={() => setBulletDecision(entryId, idx, "accept", bulletState?.editedText)}
        title="Accept suggestion (A)"
        className={`inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold transition-all duration-150 active:scale-95 ${
          isAccepted
            ? "bg-emerald-500 text-white shadow-sm shadow-emerald-200"
            : "text-slate-300 hover:bg-emerald-50 hover:text-emerald-600"
        }`}
      >
        <Check className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Accept</span>
      </button>
      <button
        onClick={() => setBulletDecision(entryId, idx, "reject", bulletState?.editedText)}
        title="Keep original (R)"
        className={`inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold transition-all duration-150 active:scale-95 ${
          isReverted
            ? "bg-red-500 text-white shadow-sm shadow-red-200"
            : "text-slate-300 hover:bg-red-50 hover:text-red-500"
        }`}
      >
        <X className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Reject</span>
      </button>
      <button
        onClick={() => setBulletDecision(entryId, idx, "edit", bulletState?.editedText ?? text)}
        title="Edit manually (E)"
        className={`inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold transition-all duration-150 active:scale-95 ${
          isEditing
            ? "bg-blue-500 text-white shadow-sm shadow-blue-200"
            : "text-slate-300 hover:bg-blue-50 hover:text-blue-500"
        }`}
      >
        <Pencil className="h-3 w-3" />
        <span className="hidden sm:inline">Edit</span>
      </button>
    </div>
  );

  // Regenerate input — always visible at the bottom of every card
  const regenerateRow = onRegenerateBullet ? (
    <div className="border-t border-border/30 px-4 py-2 flex items-center gap-2">
      <button
        onClick={() => handleRegenerate()}
        disabled={!!regeneratingBullet}
        className={`shrink-0 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-all disabled:opacity-40 ${
          isRegenerating
            ? "text-blue-500"
            : "text-slate-400 hover:text-blue-500 hover:bg-blue-50"
        }`}
      >
        <RefreshCw className={`h-3 w-3 ${isRegenerating ? "animate-spin" : ""}`} />
        {isRegenerating ? "Retrying…" : "Retry"}
      </button>
      <input
        type="text"
        value={hintInput}
        onChange={(e) => setHintInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") handleRegenerate(); }}
        placeholder="Add a note to guide the retry…"
        disabled={!!regeneratingBullet}
        className="flex-1 text-xs bg-transparent outline-none text-slate-500 placeholder:text-slate-300 disabled:opacity-50"
      />
      {hintInput && (
        <button
          onClick={handleRegenerate}
          disabled={!!regeneratingBullet}
          className="text-xs text-blue-500 hover:text-blue-700 font-medium shrink-0 disabled:opacity-50 transition-colors"
        >
          Go →
        </button>
      )}
    </div>
  ) : null;

  // Unchanged bullet — AI kept original as-is
  if (isUnchanged && !hasPlaceholder) {
    return (
      <div
        data-bullet-id={`${entryId}-${idx}`}
        className={`transition-colors duration-200 ${isFocused ? "ring-2 ring-inset ring-blue-400" : ""} ${flashBorder}`}
      >
        <div className="px-4 py-3 flex items-start gap-3">
          <p className="flex-1 text-sm text-slate-400 leading-relaxed">{original}</p>
          <span className="shrink-0 mt-0.5 text-[10px] font-medium text-slate-300 bg-slate-50 border border-slate-100 rounded-full px-2 py-0.5 whitespace-nowrap">
            no change
          </span>
        </div>
        {regenerateRow}
      </div>
    );
  }

  return (
    <div
      data-bullet-id={`${entryId}-${idx}`}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      className={`transition-colors duration-200 ${isFocused ? "ring-2 ring-inset ring-blue-400" : ""} ${flashBorder}`}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-0">
        {/* Original column */}
        <div
          className={`md:border-r border-border/50 p-4 transition-colors duration-200 ${
            isReverted ? "bg-emerald-50/60" : "bg-muted/20"
          } ${showOriginal ? "" : "hidden md:block"}`}
        >
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/40 mb-2">Original</p>
          <p className={`text-sm leading-relaxed transition-all ${isReverted ? "text-slate-700 font-medium" : "text-slate-400"}`}>
            {original ? <HighlightedText text={original} /> : <span className="italic">(no original)</span>}
          </p>
        </div>

        {/* Suggested column */}
        <div
          className={`p-4 transition-colors duration-200 ${
            isReverted
              ? "opacity-40"
              : isEditing
              ? "bg-blue-50/40"
              : isAccepted
              ? "bg-emerald-50/50"
              : "bg-card"
          }`}
        >
          {/* Header + action buttons */}
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/40">AI suggestion</p>
              {hasPlaceholder && (
                <span className="inline-flex items-center rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                  Fill in [X]
                </span>
              )}
            </div>

            {actionButtons}
          </div>

          {/* Bullet text / editor */}
          {isEditing ? (
            <>
              <textarea
                value={bulletState?.editedText || text}
                onChange={(e) => setBulletDecision(entryId, idx, "edit", e.target.value)}
                maxLength={600}
                className="w-full rounded-lg bg-card border border-border/50 focus:border-blue-300 focus:ring-2 focus:ring-blue-100 px-3 py-2.5 text-sm text-foreground leading-relaxed min-h-[72px] resize-none outline-none transition-all duration-150"
              />
              <div className="mt-1.5 flex justify-end">
                {(() => {
                  const len = (bulletState?.editedText || text).length;
                  return (
                    <p className={`text-[10px] ${len >= 500 ? "text-amber-600 font-medium" : "text-slate-400"}`}>
                      {len}/600
                    </p>
                  );
                })()}
              </div>
            </>
          ) : (
            <div className={!isReverted ? "pl-3 border-l-2 border-emerald-400/70" : ""}>
              <p
                className={`text-sm leading-relaxed transition-all ${
                  isReverted
                    ? "line-through text-slate-300"
                    : hasPlaceholder
                    ? "text-amber-800 font-medium"
                    : "text-slate-800 font-medium"
                }`}
              >
                {displayText}
              </p>
            </div>
          )}

          {/* Dropped metrics warning */}
          {dropped.length > 0 && !isReverted && (
            <p className="mt-2.5 text-[11px] text-amber-700 bg-amber-50 rounded-md px-2 py-1.5 flex items-start gap-1.5">
              <span className="shrink-0 mt-px">⚠</span>
              <span>
                Not in suggestion:{" "}
                {dropped.map((m, i) => (
                  <span key={i} className="font-semibold">{m}{i < dropped.length - 1 ? ", " : ""}</span>
                ))}
                {" "}— consider adding back
              </span>
            </p>
          )}

          {/* Mobile: show original toggle */}
          <button
            onClick={() => setShowOriginal((v) => !v)}
            className="md:hidden mt-3 text-[11px] text-slate-400 hover:text-slate-600 transition-colors"
          >
            {showOriginal ? "Hide original ▴" : "Show original ▾"}
          </button>
        </div>
      </div>

      {/* Always-visible regenerate input */}
      {regenerateRow}
    </div>
  );
}
