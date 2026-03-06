import { type BulletState, type ExperienceDiff, type TailorResult } from "./types";
import { EducationDiffSection } from "./diff/EducationDiffSection";
import { ExperienceDiffSection } from "./diff/ExperienceDiffSection";
import { SkillsDiffSection } from "./diff/SkillsDiffSection";

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
  focusedBullet?: { expId: string; idx: number } | null;
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
  focusedBullet = null,
}: DiffViewProps) {
  const sections = [
    { label: "Experience", entries: experienceDiffs },
    { label: "Projects", entries: projectDiffs },
    { label: "Leadership & Activities", entries: activityDiffs },
  ].filter((s) => s.entries.length > 0);

  return (
    <div className="space-y-6">
      {result.education_data?.length > 0 && (
        <EducationDiffSection
          educationData={result.education_data}
          manualEdits={manualEdits}
          setManualEdit={setManualEdit}
        />
      )}

      {sections.map((section) => (
        <ExperienceDiffSection
          key={section.label}
          label={section.label}
          entries={section.entries}
          result={result}
          decisions={decisions}
          setBulletDecision={setBulletDecision}
          regeneratingBullet={regeneratingBullet}
          onRegenerateBullet={onRegenerateBullet}
          focusedBullet={focusedBullet}
        />
      ))}

      {result.skills_data && Object.keys(result.skills_data).length > 0 && (
        <SkillsDiffSection
          skillsData={result.skills_data}
          manualEdits={manualEdits}
          setManualEdit={setManualEdit}
        />
      )}
    </div>
  );
}
