export interface TailoredBullet {
  text: string;
  has_placeholder: boolean;
  outcome_type: string;
}

export interface ExperienceDiff {
  type?: "experience" | "project" | "activity";
  original_bullets: string[];
  suggested_bullets: (string | TailoredBullet)[];
  changes_made: string[];
  confidence: number;
  requirements_addressed?: string[];
  coaching_note?: string;
}

export interface AtsWarning {
  field: string;
  issue: string;
  suggestion: string;
}

export interface ExperienceMeta {
  company: string | null;
  role_title: string | null;
  date_start: string | null;
  date_end: string | null;
  is_current: boolean;
}

export interface ProjectMeta {
  name: string | null;
  description: string | null;
  date_start: string | null;
  date_end: string | null;
}

export interface ActivityMeta {
  organization: string | null;
  role_title: string | null;
  date_start: string | null;
  date_end: string | null;
  is_current: boolean;
}

export interface EducationData {
  id: string;
  institution: string | null;
  degree: string | null;
  grade: string | null;
  location: string | null;
  date_start: string | null;
  date_end: string | null;
  achievements: string[];
  modules: string[];
}

export interface TailorResult {
  cv_version_id: string;
  application_id: string;
  diff_json: Record<string, ExperienceDiff>;
  experience_meta: Record<string, ExperienceMeta>;
  project_meta: Record<string, ProjectMeta>;
  activity_meta: Record<string, ActivityMeta>;
  education_data: EducationData[];
  skills_data: Record<string, string[]>;
  ats_score?: number;
  ats_warnings?: AtsWarning[];
  status: string;
}

export type BulletDecision = "accept" | "reject" | "edit";

export interface BulletState {
  decision: BulletDecision;
  editedText?: string;
}

/** Extract display text from a suggested bullet. */
export function bulletText(bullet: string | TailoredBullet): string {
  return typeof bullet === "string" ? bullet : bullet.text;
}

export function bulletHasPlaceholder(bullet: string | TailoredBullet): boolean {
  return typeof bullet === "string" ? bullet.includes("[X]") : bullet.has_placeholder;
}

export function bulletOutcomeType(bullet: string | TailoredBullet): string {
  return typeof bullet === "string" ? "" : bullet.outcome_type;
}

export interface DiffMeta {
  isProject: boolean;
  isActivity: boolean;
  title: string;
  subtitle: string;
  dateRange: string;
  sectionLabel: string;
}

export function getDiffMeta(
  id: string,
  diff: ExperienceDiff,
  result: TailorResult
): DiffMeta {
  if (diff.type === "project") {
    const pm = result.project_meta?.[id];
    return {
      isProject: true,
      isActivity: false,
      title: pm?.name || "Unknown Project",
      subtitle: pm?.description || "",
      dateRange: pm ? `${pm.date_start || "?"} \u2014 ${pm.date_end || "?"}` : "",
      sectionLabel: "Project",
    };
  }
  if (diff.type === "activity") {
    const am = result.activity_meta?.[id];
    return {
      isProject: false,
      isActivity: true,
      title: am?.role_title || "Unknown Role",
      subtitle: am?.organization || "",
      dateRange: am
        ? `${am.date_start || "?"} \u2014 ${am.is_current ? "Present" : am.date_end || "?"}`
        : "",
      sectionLabel: "Activity",
    };
  }
  const em = result.experience_meta?.[id];
  return {
    isProject: false,
    isActivity: false,
    title: em?.role_title || "Unknown Role",
    subtitle: em?.company || "",
    dateRange: em
      ? `${em.date_start || "?"} \u2014 ${em.is_current ? "Present" : em.date_end || "?"}`
      : "",
    sectionLabel: "Experience",
  };
}

export function sortByDateDesc(
  entries: [string, ExperienceDiff][],
  result: TailorResult
): [string, ExperienceDiff][] {
  return entries.sort(([idA], [idB]) => {
    const metaA = result.experience_meta?.[idA] || result.project_meta?.[idA] || result.activity_meta?.[idA];
    const metaB = result.experience_meta?.[idB] || result.project_meta?.[idB] || result.activity_meta?.[idB];
    const dateA = (metaA as unknown as Record<string, unknown>)?.date_start as string | null;
    const dateB = (metaB as unknown as Record<string, unknown>)?.date_start as string | null;
    if (!dateA && !dateB) return 0;
    if (!dateA) return 1;
    if (!dateB) return -1;
    return dateB.localeCompare(dateA);
  });
}
