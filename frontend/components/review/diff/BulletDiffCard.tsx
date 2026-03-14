import { useRef, useState } from "react";
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
  const touchStartX = useRef<number | null>(null);

  const text = bulletText(suggested);
  const hasPlaceholder = bulletHasPlaceholder(suggested);
  const isEditing = bulletState?.decision === "edit";
  const displayText = bulletState?.editedText ? bulletState.editedText : text;
  const isChanged = original !== displayText;
  const dropped = droppedMetrics(original, text);
  const isPending = !bulletState || bulletState.decision === "pending";
  const isRegenerating = regeneratingBullet?.expId === entryId && regeneratingBullet?.idx === idx;

  const SWIPE_THRESHOLD = 80; // px
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

    // Dismiss the swipe hint globally on first use
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

  const swipeFlashClass = swipeFlash === "accept"
    ? "bg-green-100 transition-colors duration-300"
    : swipeFlash === "reject"
    ? "bg-red-100 transition-colors duration-300"
    : "";

  return (
    <div
      data-bullet-id={`${entryId}-${idx}`}
      className={`grid grid-cols-1 md:grid-cols-2 gap-0 ${isPending ? "bg-orange-50/30" : ""} ${isFocused ? "ring-2 ring-inset ring-blue-400" : ""} ${swipeFlashClass}`}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Original */}
      <div className="border-b md:border-b-0 md:border-r p-3">
        <div className="text-xs font-medium text-muted-foreground mb-1">Original</div>
        <p className="text-sm">
          {original ? <HighlightedText text={original} /> : "(no original)"}
        </p>
      </div>

      {/* Suggested */}
      <div className="p-3">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">Suggested</span>
            {hasPlaceholder && (
              <span className="inline-flex items-center rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                Fill in [X]
              </span>
            )}
          </div>
          <div className="flex gap-1">
            <button
              onClick={() => setBulletDecision(entryId, idx, "accept", bulletState?.editedText)}
              className={`rounded px-2 py-0.5 text-xs ${
                bulletState?.decision === "accept"
                  ? "bg-green-100 text-green-700"
                  : "bg-muted text-muted-foreground hover:bg-green-50"
              }`}
            >
              Accept
            </button>
            <button
              onClick={() => setBulletDecision(entryId, idx, "reject", bulletState?.editedText)}
              className={`rounded px-2 py-0.5 text-xs ${
                bulletState?.decision === "reject"
                  ? "bg-red-100 text-red-700"
                  : "bg-muted text-muted-foreground hover:bg-red-50"
              }`}
            >
              Reject
            </button>
            <button
              onClick={() => setBulletDecision(entryId, idx, "edit", bulletState?.editedText ?? text)}
              className={`rounded px-2 py-0.5 text-xs ${
                bulletState?.decision === "edit"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-muted text-muted-foreground hover:bg-blue-50"
              }`}
            >
              Edit
            </button>
            {onRegenerateBullet && (
              <button
                onClick={handleRegenerate}
                disabled={regeneratingBullet !== null}
                className={`rounded px-2 py-0.5 text-xs disabled:opacity-50 ${
                  showHint
                    ? "bg-orange-100 text-orange-700"
                    : "bg-muted text-muted-foreground hover:bg-orange-50"
                }`}
                title={showHint ? "Regenerate with hint (Enter)" : "Get a new AI suggestion"}
              >
                {isRegenerating ? "…" : "↻"}
              </button>
            )}
          </div>
        </div>

        {/* Hint input */}
        {onRegenerateBullet && showHint && (
          <div className="mb-1.5 flex gap-1">
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
              placeholder="e.g. make shorter, emphasise Python… (Enter to regenerate)"
              className="flex-1 rounded border border-dashed border-orange-300 bg-orange-50/30 px-2 py-0.5 text-xs text-muted-foreground placeholder:text-muted-foreground/40 focus:border-orange-400 focus:outline-none"
            />
            <button
              onClick={() => setShowHint(false)}
              className="text-xs text-muted-foreground hover:text-foreground px-1"
              title="Cancel"
            >
              ✕
            </button>
          </div>
        )}

        {isEditing ? (
          <>
            <textarea
              value={bulletState?.editedText || text}
              onChange={(e) => setBulletDecision(entryId, idx, "edit", e.target.value)}
              maxLength={600}
              className="w-full rounded-md border px-2 py-1 text-sm min-h-[60px]"
            />
            {(() => {
              const len = (bulletState?.editedText || text).length;
              return (
                <p className={`text-right text-[10px] mt-0.5 ${len >= 500 ? "text-amber-600 font-medium" : "text-muted-foreground"}`}>
                  {len}/600
                </p>
              );
            })()}
          </>
        ) : (
          <p
            className={`text-sm ${
              bulletState?.decision === "reject"
                ? "line-through text-muted-foreground"
                : isChanged
                ? hasPlaceholder
                  ? "text-amber-800"
                  : "text-green-800"
                : ""
            }`}
          >
            {displayText}
          </p>
        )}
        {dropped.length > 0 && bulletState?.decision !== "reject" && (
          <p className="mt-1.5 text-[11px] text-amber-700 flex items-center gap-1">
            <span>⚠</span>
            <span>
              Not in suggestion:{" "}
              {dropped.map((m, i) => (
                <span key={i} className="font-semibold">{m}{i < dropped.length - 1 ? ", " : ""}</span>
              ))}
              {" "}— consider adding back when editing
            </span>
          </p>
        )}
      </div>
    </div>
  );
}
