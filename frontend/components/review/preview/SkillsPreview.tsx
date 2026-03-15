import { useState } from "react";
import { type TailorResult } from "../types";

interface SkillsPreviewProps {
  result: TailorResult;
  manualEdits?: Record<string, string>;
  setManualEdit?: (key: string, value: string) => void;
}

export function SkillsPreview({
  result,
  manualEdits = {},
  setManualEdit = () => {},
}: SkillsPreviewProps) {
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
