"use client";

import { useMemo, useState } from "react";
import type { ExperiencePool } from "@/lib/schemas";

export interface PoolSelection {
  experience_ids: string[];
  project_ids: string[];
  activity_ids: string[];
  education_ids: string[];
  skill_ids: string[];
}

interface Props {
  pool: ExperiencePool;
  onBack: () => void;
  onNext: (selection: PoolSelection) => void;
  nextLoading?: boolean;
}

export default function ExperienceSelectStep({ pool, onBack, onNext, nextLoading }: Props) {
  const allExpIds = useMemo(() => pool.work_experiences.map((e) => e.id), [pool]);
  const allProjIds = useMemo(() => pool.projects.map((p) => p.id), [pool]);
  const allActIds = useMemo(() => pool.activities.map((a) => a.id), [pool]);
  const allEduIds = useMemo(() => pool.education.map((e) => e.id), [pool]);
  const allSkillIds = useMemo(() => pool.skills.map((s) => s.id), [pool]);

  const [selectedExp, setSelectedExp] = useState<Set<string>>(new Set(allExpIds));
  const [selectedProj, setSelectedProj] = useState<Set<string>>(new Set(allProjIds));
  const [selectedAct, setSelectedAct] = useState<Set<string>>(new Set(allActIds));
  const [selectedEdu, setSelectedEdu] = useState<Set<string>>(new Set(allEduIds));
  const [selectedSkill, setSelectedSkill] = useState<Set<string>>(new Set(allSkillIds));

  const toggle = (set: Set<string>, id: string, setter: (s: Set<string>) => void) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setter(next);
  };

  // Require at least one work experience if the pool has any
  const canProceed = pool.work_experiences.length === 0 || selectedExp.size > 0;

  const handleNext = () => {
    onNext({
      experience_ids: [...selectedExp],
      project_ids: [...selectedProj],
      activity_ids: [...selectedAct],
      education_ids: [...selectedEdu],
      skill_ids: [...selectedSkill],
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Select Experiences</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Choose what the AI uses to tailor your CV. Everything is pre-selected — uncheck anything you want to exclude.
        </p>
      </div>

      {/* Work Experience */}
      {pool.work_experiences.length > 0 && (
        <Section title={`Work Experience (${selectedExp.size} / ${pool.work_experiences.length})`}>
          {pool.work_experiences.map((exp) => (
            <CheckItem
              key={exp.id}
              checked={selectedExp.has(exp.id)}
              onChange={() => toggle(selectedExp, exp.id, setSelectedExp)}
              primary={exp.role_title || "Untitled Role"}
              secondary={exp.company || ""}
              tertiary={formatDateRange(exp.date_start, exp.date_end, exp.is_current)}
            />
          ))}
        </Section>
      )}

      {/* Education */}
      {pool.education.length > 0 && (
        <Section title={`Education (${selectedEdu.size} / ${pool.education.length})`}>
          {pool.education.map((edu) => (
            <CheckItem
              key={edu.id}
              checked={selectedEdu.has(edu.id)}
              onChange={() => toggle(selectedEdu, edu.id, setSelectedEdu)}
              primary={edu.degree || "Untitled Degree"}
              secondary={edu.institution || ""}
              tertiary={formatDateRange(edu.date_start, edu.date_end)}
            />
          ))}
        </Section>
      )}

      {/* Projects */}
      {pool.projects.length > 0 && (
        <Section title={`Projects (${selectedProj.size} / ${pool.projects.length})`}>
          {pool.projects.map((proj) => (
            <CheckItem
              key={proj.id}
              checked={selectedProj.has(proj.id)}
              onChange={() => toggle(selectedProj, proj.id, setSelectedProj)}
              primary={proj.name || "Untitled Project"}
              secondary={proj.description || ""}
            />
          ))}
        </Section>
      )}

      {/* Activities */}
      {pool.activities.length > 0 && (
        <Section title={`Activities (${selectedAct.size} / ${pool.activities.length})`}>
          {pool.activities.map((act) => (
            <CheckItem
              key={act.id}
              checked={selectedAct.has(act.id)}
              onChange={() => toggle(selectedAct, act.id, setSelectedAct)}
              primary={act.role_title || act.organization || "Untitled Activity"}
              secondary={act.organization && act.role_title ? act.organization : ""}
              tertiary={formatDateRange(act.date_start, act.date_end, act.is_current)}
            />
          ))}
        </Section>
      )}

      {/* Skills */}
      {pool.skills.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">
            Skills ({selectedSkill.size} / {pool.skills.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {pool.skills.map((skill) => (
              <button
                key={skill.id}
                onClick={() => toggle(selectedSkill, skill.id, setSelectedSkill)}
                className={`inline-flex items-center rounded-full border px-3 py-1 text-sm transition-colors ${
                  selectedSkill.has(skill.id)
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-muted bg-muted/30 text-muted-foreground line-through"
                }`}
              >
                {skill.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {!canProceed && (
        <p className="text-sm text-red-600">
          Please select at least one work experience to continue.
        </p>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
        >
          Back
        </button>
        <button
          onClick={handleNext}
          disabled={!canProceed || nextLoading}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {nextLoading ? "Starting..." : "Tailor My CV"}
        </button>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
      <div className="rounded-lg border divide-y">{children}</div>
    </div>
  );
}

function CheckItem({
  checked,
  onChange,
  primary,
  secondary,
  tertiary,
}: {
  checked: boolean;
  onChange: () => void;
  primary: string;
  secondary?: string;
  tertiary?: string;
}) {
  return (
    <label className="flex items-start gap-3 px-3 py-2.5 cursor-pointer hover:bg-muted/40 transition-colors">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="mt-0.5 h-4 w-4 rounded border-gray-300 accent-primary"
      />
      <div className="min-w-0 flex-1">
        <p className={`text-sm font-medium leading-tight ${!checked ? "text-muted-foreground line-through" : ""}`}>
          {primary}
        </p>
        {secondary && (
          <p className="text-xs text-muted-foreground mt-0.5">{secondary}</p>
        )}
        {tertiary && (
          <p className="text-xs text-muted-foreground">{tertiary}</p>
        )}
      </div>
    </label>
  );
}

function formatDateRange(
  start: string | null | undefined,
  end: string | null | undefined,
  isCurrent?: boolean,
): string {
  if (!start && !end) return "";
  const s = start
    ? new Date(start).toLocaleDateString("en-GB", { month: "short", year: "numeric" })
    : "?";
  const e = isCurrent
    ? "Present"
    : end
    ? new Date(end).toLocaleDateString("en-GB", { month: "short", year: "numeric" })
    : "?";
  return `${s} – ${e}`;
}
