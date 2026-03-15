import {
  type BulletState,
  type ExperienceDiff,
  type TailorResult,
  bulletHasPlaceholder,
  bulletText,
  getDiffMeta,
} from "./types";
import { EducationPreview } from "./preview/EducationPreview";
import { SkillsPreview } from "./preview/SkillsPreview";

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
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
                              } else if (bulletState?.decision !== "edit") {
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
