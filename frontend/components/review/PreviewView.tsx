import { useState } from "react";
import {
  type BulletState,
  type ExperienceDiff,
  type TailorResult,
  bulletHasPlaceholder,
  bulletText,
  getDiffMeta,
} from "./types";

interface PreviewViewProps {
  result: TailorResult;
  experienceDiffs: [string, ExperienceDiff][];
  projectDiffs: [string, ExperienceDiff][];
  activityDiffs: [string, ExperienceDiff][];
  decisions: Record<string, Record<number, BulletState>>;
  setBulletDecision: (expId: string, idx: number, decision: "accept" | "reject" | "edit", editedText?: string) => void;
  manualEdits?: Record<string, string>;
  setManualEdit?: (key: string, value: string) => void;
}

function EducationPreview({
  result,
  manualEdits = {},
  setManualEdit = () => {},
}: {
  result: TailorResult;
  manualEdits: Record<string, string>;
  setManualEdit: (key: string, value: string) => void;
}) {
  const [editingKey, setEditingKey] = useState<string | null>(null);

  if (!result.education_data?.length) return null;
  return (
    <div>
      <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2 border-b pb-1">Education</h4>
      {result.education_data.map((edu) => (
        <div key={edu.id} className="mb-3">
          <div className="text-sm font-semibold">{edu.institution}</div>
          <div className="text-sm text-muted-foreground italic">{edu.degree}</div>
          {edu.grade && <div className="text-sm font-medium">{edu.grade}</div>}
          {edu.achievements?.map((a, i) => {
            const key = `achievement_${edu.id}_${i}`;
            const isEditing = editingKey === key;
            const value = manualEdits[key] || String(a);
            return (
              <div key={i} className="flex items-start gap-2 mb-1">
                <div className="text-sm text-muted-foreground pl-3 border-l-2 border-muted flex-1">
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
                </div>
                <button
                  onClick={() => setEditingKey(isEditing ? null : key)}
                  className="text-xs px-1.5 py-0.5 rounded hover:bg-blue-50 text-blue-600"
                >
                  {isEditing ? "✓" : "Edit"}
                </button>
              </div>
            );
          })}
          {edu.modules?.length > 0 && (
            <div className="flex items-start gap-2 mb-1">
              <div className="text-sm text-muted-foreground mt-1">
                <span className="font-medium">Coursework:</span> {edu.modules.join(", ")}
              </div>
              <button
                onClick={() => setEditingKey(`modules_${edu.id}`)}
                className="text-xs px-1.5 py-0.5 rounded hover:bg-blue-50 text-blue-600"
              >
                Edit
              </button>
              {editingKey === `modules_${edu.id}` && (
                <div className="w-full">
                  <input
                    autoFocus
                    value={manualEdits[`modules_${edu.id}`] || edu.modules.join(", ")}
                    onChange={(e) => setManualEdit(`modules_${edu.id}`, e.target.value)}
                    onBlur={() => setEditingKey(null)}
                    className="w-full rounded px-1 py-0.5 text-sm border"
                  />
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function SkillsPreview({
  result,
  manualEdits = {},
  setManualEdit = () => {},
}: {
  result: TailorResult;
  manualEdits: Record<string, string>;
  setManualEdit: (key: string, value: string) => void;
}) {
  const [editingKey, setEditingKey] = useState<string | null>(null);

  if (!result.skills_data || Object.keys(result.skills_data).length === 0) return null;
  return (
    <div>
      <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2 border-b pb-1">
        Technical Skills
      </h4>
      {Object.entries(result.skills_data).map(([category, skills]) => {
        const key = `skills_${category}`;
        const isEditing = editingKey === key;
        const value = manualEdits[key] || skills.join(", ");
        return (
          <div key={category} className="flex items-center gap-2 mb-1">
            <div className="text-sm">
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
              className="text-xs px-1.5 py-0.5 rounded hover:bg-blue-50 text-blue-600 ml-auto"
            >
              {isEditing ? "✓" : "Edit"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default function PreviewView({
  result,
  experienceDiffs,
  projectDiffs,
  activityDiffs,
  decisions,
  setBulletDecision,
  manualEdits = {},
  setManualEdit = () => {},
}: PreviewViewProps) {
  const sections = [
    { label: "Experience", entries: experienceDiffs },
    { label: "Projects", entries: projectDiffs },
    { label: "Leadership & Activities", entries: activityDiffs },
  ].filter((s) => s.entries.length > 0);

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* Original Resume */}
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">Original</h3>
        <div className="space-y-4 rounded-lg border p-4 bg-white">
          <EducationPreview result={result} />
          {sections.map((section) => (
            <div key={section.label}>
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2 border-b pb-1">{section.label}</h4>
              {section.entries.map(([id, diff]) => {
                const meta = getDiffMeta(id, diff, result);
                return (
                  <div key={id} className="mb-3">
                    <div className="mb-1">
                      <span className="text-sm font-semibold">{meta.title}</span>
                      {meta.subtitle && (
                        <span className="text-sm text-muted-foreground">
                          {" "}{meta.isProject ? "" : "at "}{meta.subtitle}
                        </span>
                      )}
                    </div>
                    <ul className="space-y-1">
                      {diff.original_bullets.map((bullet, idx) => (
                        <li key={idx} className="text-sm text-muted-foreground pl-3 border-l-2 border-muted">
                          {bullet}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          ))}
          <SkillsPreview result={result} />
        </div>
      </div>

      {/* Tailored Resume */}
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">Tailored</h3>
        <div className="space-y-4 rounded-lg border p-4 bg-white">
          <EducationPreview result={result} manualEdits={manualEdits} setManualEdit={setManualEdit} />
          {sections.map((section) => (
            <div key={section.label}>
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2 border-b pb-1">{section.label}</h4>
              {section.entries.map(([id, diff]) => {
                const meta = getDiffMeta(id, diff, result);
                return (
                  <div key={id} className="mb-3">
                    <div className="mb-1">
                      <span className="text-sm font-semibold">{meta.title}</span>
                      {meta.subtitle && (
                        <span className="text-sm text-muted-foreground">
                          {" "}{meta.isProject ? "" : "at "}{meta.subtitle}
                        </span>
                      )}
                    </div>
                    <ul className="space-y-1">
                      {diff.suggested_bullets.map((suggested, idx) => {
                        const original = diff.original_bullets[idx] || "";
                        const text = bulletText(suggested);
                        const hasPlaceholder = bulletHasPlaceholder(suggested);
                        const bulletState = decisions[id]?.[idx];
                        const isRejected = bulletState?.decision === "reject";
                        const displayText = bulletState?.editedText
                          ? bulletState.editedText
                          : isRejected
                          ? original
                          : text;
                        const isChanged = original !== displayText;

                        return (
                          <li
                            key={idx}
                            onClick={() => {
                              if (isRejected) {
                                setBulletDecision(id, idx, "accept");
                              } else if (!isEdited) {
                                setBulletDecision(id, idx, "reject");
                              }
                            }}
                            className={`text-sm pl-3 border-l-2 cursor-pointer transition-colors ${
                              isRejected
                                ? "border-red-300 text-muted-foreground"
                                : isChanged
                                ? hasPlaceholder
                                  ? "border-amber-400 text-amber-900"
                                  : "border-green-400 text-green-900"
                                : "border-muted text-foreground"
                            }`}
                            title={isRejected ? "Click to accept" : "Click to reject"}
                          >
                            {displayText}
                            {isRejected && (
                              <span className="ml-1 text-[10px] text-red-400">(rejected)</span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })}
            </div>
          ))}
          <SkillsPreview result={result} manualEdits={manualEdits} setManualEdit={setManualEdit} />
        </div>
      </div>
    </div>
  );
}
