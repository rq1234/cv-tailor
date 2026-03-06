import { useState } from "react";
import type { TailorResult } from "../types";

type EducationItem = TailorResult["education_data"][number];

interface EducationDiffSectionProps {
  educationData: EducationItem[];
  manualEdits: Record<string, string>;
  setManualEdit: (key: string, value: string) => void;
}

export function EducationDiffSection({
  educationData,
  manualEdits,
  setManualEdit,
}: EducationDiffSectionProps) {
  const [editingKey, setEditingKey] = useState<string | null>(null);

  return (
    <div>
      <h2 className="text-lg font-bold mb-3">Education</h2>
      {educationData.map((edu) => (
        <div key={edu.id} className="rounded-lg border mb-4 bg-muted/30">
          <div className="px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold">{edu.institution || "Institution"}</span>
                {edu.location && (
                  <span className="ml-2 text-xs text-muted-foreground">{edu.location}</span>
                )}
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
                    <span className="font-medium">Coursework:</span>{" "}
                    {manualEdits[`modules_${edu.id}`] || edu.modules.join(", ")}
                  </span>
                )}
                <button
                  onClick={() =>
                    setEditingKey(
                      editingKey === `modules_${edu.id}` ? null : `modules_${edu.id}`
                    )
                  }
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
  );
}
