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

interface DiffViewProps {
  result: TailorResult;
  experienceDiffs: [string, ExperienceDiff][];
  projectDiffs: [string, ExperienceDiff][];
  activityDiffs: [string, ExperienceDiff][];
  decisions: Record<string, Record<number, BulletState>>;
  setBulletDecision: (expId: string, idx: number, decision: "accept" | "reject" | "edit", editedText?: string) => void;
  manualEdits?: Record<string, string>;
  setManualEdit?: (key: string, value: string) => void;
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
}: DiffViewProps) {
  const [editingKey, setEditingKey] = useState<string | null>(null);

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
      {sections.map((section) => (
        <div key={section.label}>
          <h2 className="text-lg font-bold mb-3">{section.label}</h2>
          {section.entries.map(([entryId, diff]) => {
            const meta = getDiffMeta(entryId, diff, result);
            return (
              <div key={entryId} className="rounded-lg border mb-4">
                <div className="border-b bg-muted/50 px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-semibold">{meta.title}</span>
                      {meta.subtitle && (
                        <span className="text-sm text-muted-foreground"> {meta.isProject ? "" : "at "}{meta.subtitle}</span>
                      )}
                      {meta.dateRange && (
                        <span className="ml-2 text-xs text-muted-foreground">({meta.dateRange})</span>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      Confidence: {(diff.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  {diff.requirements_addressed && diff.requirements_addressed.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {diff.requirements_addressed.map((req, i) => (
                        <span key={i} className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs text-green-700">
                          {req}
                        </span>
                      ))}
                    </div>
                  )}
                  {diff.changes_made.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {diff.changes_made.map((change, i) => (
                        <span key={i} className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                          {change}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

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

                    return (
                      <div key={idx} className="grid grid-cols-2 gap-0">
                        {/* Original */}
                        <div className="border-r p-3">
                          <div className="text-xs font-medium text-muted-foreground mb-1">Original</div>
                          <p className="text-sm">{original || "(no original)"}</p>
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
                            </div>
                          </div>

                          {isEditing ? (
                            <textarea
                              value={bulletState?.editedText || text}
                              onChange={(e) => setBulletDecision(entryId, idx, "edit", e.target.value)}
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
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ))}

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
