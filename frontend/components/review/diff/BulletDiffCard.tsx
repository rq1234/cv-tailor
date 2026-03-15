import { useRef, useState } from "react";
import { Check, X, Pencil, RefreshCw } from "lucide-react";
import {
  type BulletState,
  type ExperienceDiff,
  bulletHasPlaceholder,
  bulletText,
} from "../types";

// Matches: 50%, $3.2B, £1.4m, 1,400, 500k, 3.2x, numbers like 1400
// Uses \d+(?:,\d+)* for thousands separators to avoid matching trailing commas in "EC2," or "S3,"
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
  const [showHint, setShowHint] = useState(false);
  const [swipeFlash, setSwipeFlash] = useState<"accept" | "reject" | null>(null);
  const [clickFlash, setClickFlash] = useState<"accept" | "reject" | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const touchStartX = useRef<number | null>(null);

  const flashClick = (dir: "accept" | "reject") => {
    setClickFlash(dir);
    setTimeout(() => setClickFlash(null), 300);
  };

  const text = bulletText(suggested);
  const hasPlaceholder = bulletHasPlaceholder(suggested);
  const isEditing = bulletState?.decision === "edit";
  const isAccepted = bulletState?.decision === "accept";
  const isRejected = bulletState?.decision === "reject";
  const isPending = !bulletState || bulletState.decision === "pending";
  const displayText = bulletState?.editedText ? bulletState.editedText : text;
  const isChanged = original !== displayText;
  const dropped = droppedMetrics(original, text);
  const isRegenerating = regeneratingBullet?.expId === entryId && regeneratingBullet?.idx === idx;

  const SWIPE_THRESHOLD = 80;
  const SWIPE_HINT_KEY = "swipe-hint-dismissed";

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
    try { localStorage.setItem(SWIPE_HINT_KEY, "1"); } catch { /* ignore */ }
  };

  const handleRegenerate = () => {
    if (showHint) {
      onRegenerateBullet?.(entryId, idx, hintInput.trim() || undefined);
      setHintInput("");
      setShowHint(false);
    } else {
      setShowHint(true);
    }
  };

  // Outer flash overlay
  const flashOverlay =
    swipeFlash === "accept" || clickFlash === "accept"
      ? "ring-2 ring-inset ring-emerald-300 bg-emerald-50/40"
      : swipeFlash === "reject" || clickFlash === "reject"
      ? "ring-2 ring-inset ring-red-300 bg-red-50/40"
      : "";

  // Row background based on decision
  const rowBg = isAccepted
    ? "bg-emerald-50/30"
    : isRejected
    ? "bg-red-50/20"
    : isEditing
    ? "bg-blue-50/20"
    : isPending
    ? "bg-orange-50/20"
    : "";

  return (
    <div
      data-bullet-id={`${entryId}-${idx}`}
      className={`grid grid-cols-1 md:grid-cols-2 gap-0 transition-colors duration-200 ${rowBg} ${isFocused ? "ring-2 ring-inset ring-blue-400" : ""} ${flashOverlay}`}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Original column */}
      <div className={`md:border-r border-slate-100 p-4 ${showOriginal ? "border-b md:border-b-0" : "hidden md:block"}`}>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Original</p>
        <p className={`text-sm text-slate-500 leading-relaxed ${isAccepted ? "opacity-50" : ""}`}>
          {original ? <HighlightedText text={original} /> : <span className="italic">(no original)</span>}
        </p>
      </div>

      {/* Suggested column */}
      <div className="p-4">
        {/* Header: label + decision buttons */}
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Suggested</p>
            {hasPlaceholder && (
              <span className="inline-flex items-center rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                Fill in [X]
              </span>
            )}
          </div>

          {/* Decision buttons */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => { setBulletDecision(entryId, idx, "accept", bulletState?.editedText); flashClick("accept"); }}
              title="Accept (A)"
              className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all duration-150 active:scale-95 ${
                isAccepted
                  ? "bg-emerald-500 text-white shadow-sm"
                  : "text-slate-400 hover:bg-emerald-50 hover:text-emerald-600"
              }`}
            >
              <Check className="h-3 w-3" />
              <span className="hidden sm:inline">Accept</span>
            </button>
            <button
              onClick={() => { setBulletDecision(entryId, idx, "reject", bulletState?.editedText); flashClick("reject"); }}
              title="Reject (R)"
              className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all duration-150 active:scale-95 ${
                isRejected
                  ? "bg-red-500 text-white shadow-sm"
                  : "text-slate-400 hover:bg-red-50 hover:text-red-600"
              }`}
            >
              <X className="h-3 w-3" />
              <span className="hidden sm:inline">Reject</span>
            </button>
            <button
              onClick={() => setBulletDecision(entryId, idx, "edit", bulletState?.editedText ?? text)}
              title="Edit (E)"
              className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all duration-150 active:scale-95 ${
                isEditing
                  ? "bg-blue-500 text-white shadow-sm"
                  : "text-slate-400 hover:bg-blue-50 hover:text-blue-600"
              }`}
            >
              <Pencil className="h-3 w-3" />
              <span className="hidden sm:inline">Edit</span>
            </button>
          </div>
        </div>

        {/* Bullet text / editor */}
        {isEditing ? (
          <>
            <textarea
              value={bulletState?.editedText || text}
              onChange={(e) => setBulletDecision(entryId, idx, "edit", e.target.value)}
              maxLength={600}
              className="w-full rounded-lg bg-white border border-slate-200 focus:border-blue-300 focus:ring-1 focus:ring-blue-200 px-3 py-2 text-sm text-slate-800 leading-relaxed min-h-[72px] resize-none outline-none transition-colors"
            />
            <div className="flex items-center justify-between mt-1.5">
              {(() => {
                const len = (bulletState?.editedText || text).length;
                return (
                  <p className={`text-[10px] ${len >= 500 ? "text-amber-600 font-medium" : "text-slate-400"}`}>
                    {len}/600
                  </p>
                );
              })()}
              {onRegenerateBullet && !showHint && (
                <button
                  onClick={() => setShowHint(true)}
                  disabled={regeneratingBullet !== null}
                  className="inline-flex items-center gap-1 text-[10px] text-slate-400 hover:text-blue-600 transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`h-2.5 w-2.5 ${isRegenerating ? "animate-spin" : ""}`} />
                  Regenerate with hint
                </button>
              )}
            </div>
            {onRegenerateBullet && showHint && (
              <div className="mt-1.5 flex gap-1">
                <input
                  autoFocus
                  type="text"
                  value={hintInput}
                  onChange={(e) => setHintInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      onRegenerateBullet(entryId, idx, hintInput.trim() || undefined);
                      setHintInput("");
                      setShowHint(false);
                    }
                    if (e.key === "Escape") setShowHint(false);
                  }}
                  placeholder="e.g. make shorter, emphasise Python… (Enter)"
                  className="flex-1 rounded-lg border border-dashed border-blue-200 bg-blue-50/40 px-2.5 py-1 text-xs text-slate-600 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none transition-colors"
                />
                <button
                  onClick={() => setShowHint(false)}
                  className="text-xs text-slate-400 hover:text-slate-600 px-1 transition-colors"
                  title="Cancel"
                >
                  ✕
                </button>
              </div>
            )}
          </>
        ) : (
          <p
            className={`text-sm leading-relaxed transition-all ${
              isRejected
                ? "line-through text-slate-400"
                : isAccepted
                ? isChanged
                  ? hasPlaceholder
                    ? "text-amber-800"
                    : "text-emerald-800 font-medium"
                  : "text-slate-700"
                : isChanged
                ? hasPlaceholder
                  ? "text-amber-800"
                  : "text-slate-800"
                : "text-slate-600"
            }`}
          >
            {displayText}
          </p>
        )}

        {/* Dropped metrics warning */}
        {dropped.length > 0 && !isRejected && (
          <p className="mt-2 text-[11px] text-amber-700 flex items-start gap-1.5">
            <span className="shrink-0 mt-px">⚠</span>
            <span>
              Not in suggestion:{" "}
              {dropped.map((m, i) => (
                <span key={i} className="font-semibold">{m}{i < dropped.length - 1 ? ", " : ""}</span>
              ))}
              {" "}— consider adding back when editing
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
  );
}
