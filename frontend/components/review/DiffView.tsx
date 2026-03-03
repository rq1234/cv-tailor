import { useState } from "react";
import {
  type BulletState,
  type ExperienceDiff,
  type TailorResult,
  bulletHasPlaceholder,
  bulletOutcomeType,
  bulletText,
  getDiffMeta,
} from "./types";

// Matches: 50%, $3.2B, £1.4m, 1,400, 500k, 3.2x, numbers like 1400
const METRIC_RE = /(\$|£|€)?[\d,]+\.?\d*(%|[xX]|[kKmMbBtT]n?)?(?:\+)?|\d+\.?\d*(%|[xX])/g;

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

interface DiffViewProps {
  result: TailorResult;
  experienceDiffs: [string, ExperienceDiff][];
  projectDiffs: [string, ExperienceDiff][];
  activityDiffs: [string, ExperienceDiff][];
  decisions: Record<string, Record<number, BulletState>>;
  setBulletDecision: (expId: string, idx: number, decision: "accept" | "reject" | "edit", editedText?: string) => void;
  manualEdits?: Record<string, string>;
  setManualEdit?: (key: string, value: string) => void;
  regeneratingBullet?: { expId: string; idx: number } | null;
  onRegenerateBullet?: (expId: string, idx: number, hint?: string) => void;
}

export default function DiffView({
  result,
  experienceDiffs,
  projectDiffs,
  activityDiffs,
  decisions,
  setBulletDecision,
  manualEdits = {},
  setManualEdit = () => {},
  regeneratingBullet = null,
  onRegenerateBullet,
}: DiffViewProps) {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [hintInputs, setHintInputs] = useState<Record<string, string>>({});
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [showHintFor, setShowHintFor] = useState<string | null>(null);

  const toggleCollapsed = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const collapseSection = (ids: string[]) =>
    setCollapsed((prev) => new Set([...prev, ...ids]));

  const expandSection = (ids: string[]) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.delete(id));
      return next;
    });

  const sections = [
    { label: "Experience", entries: experienceDiffs },
    { label: "Projects", entries: projectDiffs },
    { label: "Leadership & Activities", entries: activityDiffs },
  ].filter((s) => s.entries.length > 0);

  return (
    <div className="space-y-6">
      {/* Education Section (editable) */}
      {result.education_data?.length > 0 && (
        <div>
          <h2 className="text-lg font-bold mb-3">Education</h2>
          {result.education_data.map((edu) => (
            <div key={edu.id} className="rounded-lg border mb-4 bg-muted/30">
              <div className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-semibold">{edu.institution || "Institution"}</span>
                    {edu.location && <span className="ml-2 text-xs text-muted-foreground">{edu.location}</span>}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {edu.date_start || ""} &mdash; {edu.date_end || ""}
                  </span>
                </div>
                <div className="text-sm text-muted-foreground italic">{edu.degree || ""}</div>
                {edu.grade && <div className="text-xs text-muted-foreground mt-1">{edu.grade}</div>}
                {edu.achievements?.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {edu.achievements.map((a, i) => {
                      const key = `achievement_${edu.id}_${i}`;
                      const isEditing = editingKey === key;
                      const value = manualEdits[key] || String(a);
                      return (
                        <li key={i} className="flex items-start gap-2 mb-1">
                          <span className="text-sm pl-3 border-l-2 border-muted text-muted-foreground flex-1">
                            {isEditing ? (
                              <input
                                autoFocus
                                value={value}
                                onChange={(e) => setManualEdit(key, e.target.value)}
                                onBlur={() => setEditingKey(null)}
                                onKeyDown={(e) => e.key === "Enter" && setEditingKey(null)}
                                className="w-full rounded px-1 py-0.5 text-sm border"
                              />
                            ) : (
                              value
                            )}
                          </span>
                          <button
                            onClick={() => setEditingKey(isEditing ? null : key)}
                            className="text-xs px-1.5 py-0.5 rounded hover:bg-blue-50 text-blue-600 whitespace-nowrap"
                          >
                            {isEditing ? "✓" : "Edit"}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
                {edu.modules?.length > 0 && (
                  <div className="flex items-center gap-2 mt-2">
                    {editingKey === `modules_${edu.id}` ? (
                      <input
                        autoFocus
                        value={manualEdits[`modules_${edu.id}`] || edu.modules.join(", ")}
                        onChange={(e) => setManualEdit(`modules_${edu.id}`, e.target.value)}
                        onBlur={() => setEditingKey(null)}
                        onKeyDown={(e) => e.key === "Enter" && setEditingKey(null)}
                        className="w-full rounded px-1 py-0.5 text-sm border"
                      />
                    ) : (
                      <span className="text-sm text-muted-foreground flex-1">
                        <span className="font-medium">Coursework:</span> {manualEdits[`modules_${edu.id}`] || edu.modules.join(", ")}
                      </span>
                    )}
                    <button
                      onClick={() => setEditingKey(editingKey === `modules_${edu.id}` ? null : `modules_${edu.id}`)}
                      className="text-xs px-1.5 py-0.5 rounded hover:bg-blue-50 text-blue-600 whitespace-nowrap"
                    >
                      {editingKey === `modules_${edu.id}` ? "✓" : "Edit"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Diff sections */}
      {sections.map((section) => {
        const sectionIds = section.entries.map(([id]) => id);
        const allCollapsed = sectionIds.length > 0 && sectionIds.every((id) => collapsed.has(id));
        return (
          <div key={section.label}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold">{section.label}</h2>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => section.entries.forEach(([entryId, diff]) => {
                    for (let i = 0; i < diff.suggested_bullets.length; i++) setBulletDecision(entryId, i, "accept");
                  })}
                  className="text-xs text-emerald-600 hover:text-emerald-700 underline"
                >
                  Accept all
                </button>
                <button
                  onClick={() => section.entries.forEach(([entryId, diff]) => {
                    for (let i = 0; i < diff.suggested_bullets.length; i++) setBulletDecision(entryId, i, "reject");
                  })}
                  className="text-xs text-red-500 hover:text-red-600 underline"
                >
                  Reject all
                </button>
                <button
                  onClick={() => allCollapsed ? expandSection(sectionIds) : collapseSection(sectionIds)}
                  className="text-xs text-muted-foreground hover:text-foreground underline"
                >
                  {allCollapsed ? "Expand all" : "Collapse all"}
                </button>
              </div>
            </div>
            {section.entries.map(([entryId, diff]) => {
              const meta = getDiffMeta(entryId, diff, result);
              const borderColour =
                diff.confidence >= 0.85 ? "border-green-200"
                : diff.confidence < 0.70 ? "border-amber-200"
                : "border-gray-200";
              const isCollapsed = collapsed.has(entryId);
              return (
                <div key={entryId} className={`rounded-lg border mb-4 ${borderColour}`}>
                  {/* Card header — click to collapse/expand */}
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
                            <span className="text-sm text-muted-foreground"> {meta.isProject ? "" : "at "}{meta.subtitle}</span>
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
                          <span key={i} className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                            {change}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Bullet diffs — hidden when collapsed */}
                  {!isCollapsed && (
                    <div className="divide-y">
                      {diff.suggested_bullets.map((suggested, idx) => {
                        const original = diff.original_bullets[idx] || "";
                        const text = bulletText(suggested);
                        const hasPlaceholder = bulletHasPlaceholder(suggested);
                        const outcomeType = bulletOutcomeType(suggested);
                        const bulletState = decisions[entryId]?.[idx];
                        const isEditing = bulletState?.decision === "edit";
                        const displayText = bulletState?.editedText ? bulletState.editedText : text;
                        const isChanged = original !== displayText;

                        const dropped = droppedMetrics(original, text);
                        const hintKey = `${entryId}_${idx}`;

                        const isPending = !bulletState || bulletState.decision === "pending";

                        return (
                          <div key={idx} className={`grid grid-cols-1 md:grid-cols-2 gap-0 ${isPending ? "bg-orange-50/30" : ""}`}>
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
                                  {outcomeType && outcomeType !== "process" && (
                                    <span className="inline-flex items-center rounded-full bg-purple-50 px-1.5 py-0.5 text-[10px] text-purple-600">
                                      {outcomeType}
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
                                      onClick={() => {
                                        if (showHintFor === hintKey) {
                                          // Hint is open — regenerate with whatever hint was typed
                                          const hint = hintInputs[hintKey]?.trim() || undefined;
                                          onRegenerateBullet(entryId, idx, hint);
                                          setHintInputs((prev) => ({ ...prev, [hintKey]: "" }));
                                          setShowHintFor(null);
                                        } else {
                                          setShowHintFor(hintKey);
                                        }
                                      }}
                                      disabled={regeneratingBullet !== null}
                                      className={`rounded px-2 py-0.5 text-xs disabled:opacity-50 ${
                                        showHintFor === hintKey
                                          ? "bg-orange-100 text-orange-700"
                                          : "bg-muted text-muted-foreground hover:bg-orange-50"
                                      }`}
                                      title={showHintFor === hintKey ? "Regenerate with hint (Enter)" : "Get a new AI suggestion"}
                                    >
                                      {regeneratingBullet?.expId === entryId && regeneratingBullet?.idx === idx
                                        ? "…"
                                        : "↻"}
                                    </button>
                                  )}
                                </div>
                              </div>

                              {/* Hint input — only shown when user clicks ↻ */}
                              {onRegenerateBullet && showHintFor === hintKey && (
                                <div className="mb-1.5 flex gap-1">
                                  <input
                                    autoFocus
                                    type="text"
                                    value={hintInputs[hintKey] ?? ""}
                                    onChange={(e) => setHintInputs((prev) => ({ ...prev, [hintKey]: e.target.value }))}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter" && onRegenerateBullet) {
                                        const hint = hintInputs[hintKey]?.trim() || undefined;
                                        onRegenerateBullet(entryId, idx, hint);
                                        setHintInputs((prev) => ({ ...prev, [hintKey]: "" }));
                                        setShowHintFor(null);
                                      }
                                      if (e.key === "Escape") setShowHintFor(null);
                                    }}
                                    placeholder="e.g. make shorter, emphasise Python… (Enter to regenerate)"
                                    className="flex-1 rounded border border-dashed border-orange-300 bg-orange-50/30 px-2 py-0.5 text-xs text-muted-foreground placeholder:text-muted-foreground/40 focus:border-orange-400 focus:outline-none"
                                  />
                                  <button
                                    onClick={() => setShowHintFor(null)}
                                    className="text-xs text-muted-foreground hover:text-foreground px-1"
                                    title="Cancel"
                                  >
                                    ✕
                                  </button>
                                </div>
                              )}

                              {isEditing ? (
                                <textarea
                                  value={bulletState?.editedText || text}
                                  onChange={(e) => setBulletDecision(entryId, idx, "edit", e.target.value)}
                                  maxLength={600}
                                  className="w-full rounded-md border px-2 py-1 text-sm min-h-[60px]"
                                />
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
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })}

      {/* Technical Skills (editable) */}
      {result.skills_data && Object.keys(result.skills_data).length > 0 && (
        <div>
          <h2 className="text-lg font-bold mb-3">Technical Skills</h2>
          <div className="rounded-lg border bg-muted/30 px-4 py-3 space-y-2">
            {Object.entries(result.skills_data).map(([category, skills]) => {
              const key = `skills_${category}`;
              const isEditing = editingKey === key;
              const value = manualEdits[key] || skills.join(", ");
              return (
                <div key={category} className="flex items-center gap-2">
                  <div className="text-sm flex-1">
                    <span className="font-semibold">{category}:</span>{" "}
                    {isEditing ? (
                      <input
                        autoFocus
                        value={value}
                        onChange={(e) => setManualEdit(key, e.target.value)}
                        onBlur={() => setEditingKey(null)}
                        onKeyDown={(e) => e.key === "Enter" && setEditingKey(null)}
                        className="w-full rounded px-1 py-0.5 text-sm border"
                      />
                    ) : (
                      <span className="text-muted-foreground">{value}</span>
                    )}
                  </div>
                  <button
                    onClick={() => setEditingKey(isEditing ? null : key)}
                    className="text-xs px-1.5 py-0.5 rounded hover:bg-blue-50 text-blue-600 whitespace-nowrap"
                  >
                    {isEditing ? "✓" : "Edit"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
