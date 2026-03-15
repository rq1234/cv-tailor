import { useState } from "react";
import { type TailorResult } from "../types";

interface EducationPreviewProps {
  result: TailorResult;
  manualEdits?: Record<string, string>;
  setManualEdit?: (key: string, value: string) => void;
}

export function EducationPreview({
  result,
  manualEdits = {},
  setManualEdit = () => {},
}: EducationPreviewProps) {
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
