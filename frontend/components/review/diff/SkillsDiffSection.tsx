import { useState } from "react";

interface SkillsDiffSectionProps {
  skillsData: Record<string, string[]>;
  manualEdits: Record<string, string>;
  setManualEdit: (key: string, value: string) => void;
}

export function SkillsDiffSection({
  skillsData,
  manualEdits,
  setManualEdit,
}: SkillsDiffSectionProps) {
  const [editingKey, setEditingKey] = useState<string | null>(null);

  return (
    <div>
      <h2 className="text-lg font-bold mb-3">Technical Skills</h2>
      <div className="rounded-lg border bg-muted/30 px-4 py-3 space-y-2">
        {Object.entries(skillsData).map(([category, skills]) => {
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
  );
}
