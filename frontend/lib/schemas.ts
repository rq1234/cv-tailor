/**
 * Zod schemas mirroring Pydantic models.
 */

import { z } from "zod";

// ── CV Upload ──────────────────────────────────────────────────────────
export const reviewItemSchema = z.object({
  id: z.string().uuid(),
  table: z.string(),
  field: z.string(),
  current_value: z.string().nullable(),
  confidence: z.number(),
  review_reason: z.string().nullable(),
});

export const unclassifiedBlockSchema = z.object({
  id: z.string().uuid(),
  raw_text: z.string(),
  gpt_category_guess: z.string().nullable(),
  gpt_confidence: z.number().nullable(),
});

export const duplicateItemSchema = z.object({
  id: z.string().uuid(),
  company: z.string().nullable().optional(),
  role_title: z.string().nullable().optional(),
  similarity_score: z.number().nullable(),
  is_primary_variant: z.boolean(),
});

export const duplicateGroupSchema = z.object({
  variant_group_id: z.string().uuid(),
  items: z.array(duplicateItemSchema),
});

export const parseSummarySchema = z.object({
  upload_id: z.string().uuid(),
  cleanly_parsed_count: z.number(),
  needs_review: z.array(reviewItemSchema),
  unclassified_blocks: z.array(unclassifiedBlockSchema),
  duplicates: z.array(duplicateGroupSchema),
});

// ── Experience Pool ────────────────────────────────────────────────────
export const workExperienceSchema = z.object({
  id: z.string().uuid(),
  company: z.string().nullable(),
  role_title: z.string().nullable(),
  location: z.string().nullable(),
  date_start: z.string().nullable(),
  date_end: z.string().nullable(),
  is_current: z.boolean(),
  bullets: z.union([
    z.array(z.union([
      z.object({ text: z.string(), domain_tags: z.array(z.string()).optional() }),
      z.string(),
    ])),
    z.record(z.string(), z.unknown()),
  ]),
  domain_tags: z.array(z.string()).nullable(),
  skill_tags: z.array(z.string()).nullable(),
  variant_group_id: z.string().uuid().nullable(),
  is_primary_variant: z.boolean(),
  needs_review: z.boolean(),
  review_reason: z.string().nullable(),
});

export const educationSchema = z.object({
  id: z.string().uuid(),
  institution: z.string().nullable(),
  degree: z.string().nullable(),
  grade: z.string().nullable(),
  date_start: z.string().nullable(),
  date_end: z.string().nullable(),
  location: z.string().nullable(),
  achievements: z.union([z.array(z.string()), z.record(z.string(), z.unknown())]).nullable(),
  modules: z.union([z.array(z.string()), z.record(z.string(), z.unknown())]).nullable(),
  needs_review: z.boolean(),
});

const bulletSchema = z.union([
  z.object({ text: z.string(), domain_tags: z.array(z.string()).optional() }),
  z.string(),
]);

export const projectSchema = z.object({
  id: z.string().uuid(),
  name: z.string().nullable(),
  description: z.string().nullable(),
  date_start: z.string().nullable(),
  date_end: z.string().nullable(),
  url: z.string().nullable(),
  bullets: z.union([z.array(bulletSchema), z.record(z.string(), z.unknown())]).nullable(),
  domain_tags: z.array(z.string()).nullable(),
  skill_tags: z.array(z.string()).nullable(),
  variant_group_id: z.string().uuid().nullable().optional(),
  is_primary_variant: z.boolean().optional().default(true),
  needs_review: z.boolean(),
});

export const activitySchema = z.object({
  id: z.string().uuid(),
  organization: z.string().nullable(),
  role_title: z.string().nullable(),
  location: z.string().nullable(),
  date_start: z.string().nullable(),
  date_end: z.string().nullable(),
  is_current: z.boolean(),
  bullets: z.union([z.array(bulletSchema), z.record(z.string(), z.unknown())]),
  domain_tags: z.array(z.string()).nullable(),
  skill_tags: z.array(z.string()).nullable(),
  variant_group_id: z.string().uuid().nullable(),
  is_primary_variant: z.boolean(),
  needs_review: z.boolean(),
  review_reason: z.string().nullable(),
});

export const skillSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  canonical_name: z.string().nullable(),
  category: z.string().nullable(),
  proficiency: z.string().nullable(),
  domain_tags: z.array(z.string()).nullable(),
});

export const profileSchema = z.object({
  id: z.string().uuid(),
  full_name: z.string().nullable(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  location: z.string().nullable(),
  linkedin_url: z.string().nullable(),
  portfolio_url: z.string().nullable(),
  summary: z.string().nullable(),
});

export const experiencePoolSchema = z.object({
  profile: profileSchema.nullable(),
  work_experiences: z.array(workExperienceSchema),
  education: z.array(educationSchema),
  projects: z.array(projectSchema),
  activities: z.array(activitySchema),
  skills: z.array(skillSchema),
});

// ── Application input validation ────────────────────────────────────────
/** Must match backend ApplicationCreate.jd_raw max_length. */
export const JD_MAX_CHARS = 50_000;
export const jdRawSchema = z
  .string()
  .min(1, "Job description is required")
  .max(JD_MAX_CHARS, `Job description must be under ${JD_MAX_CHARS.toLocaleString()} characters`);

// ── Applications ───────────────────────────────────────────────────────
export const OUTCOME_OPTIONS = [
  { value: "applied",   label: "Applied",     className: "text-blue-700 bg-blue-50" },
  { value: "interview", label: "Interviewing", className: "text-purple-700 bg-purple-50" },
  { value: "offer",     label: "Offer",        className: "text-green-700 bg-green-50" },
  { value: "rejected",  label: "Rejected",     className: "text-red-700 bg-red-50" },
  { value: "withdrawn", label: "Withdrawn",    className: "text-gray-600 bg-gray-100" },
] as const;

export type OutcomeValue = typeof OUTCOME_OPTIONS[number]["value"];

export const applicationSchema = z.object({
  id: z.string().uuid(),
  company_name: z.string(),
  role_title: z.string().nullable(),
  jd_raw: z.string(),
  jd_parsed: z.record(z.string(), z.any()).nullable(),
  jd_source: z.string().nullable(),
  status: z.string(),
  outcome: z.string().nullable(),
  created_at: z.string(),
});

// ── Types ──────────────────────────────────────────────────────────────
export type ReviewItem = z.infer<typeof reviewItemSchema>;
export type UnclassifiedBlock = z.infer<typeof unclassifiedBlockSchema>;
export type ParseSummary = z.infer<typeof parseSummarySchema>;
export type WorkExperience = z.infer<typeof workExperienceSchema>;
export type Education = z.infer<typeof educationSchema>;
export type Project = z.infer<typeof projectSchema>;
export type Activity = z.infer<typeof activitySchema>;
export type Skill = z.infer<typeof skillSchema>;
export type CvProfile = z.infer<typeof profileSchema>;
export type ExperiencePool = z.infer<typeof experiencePoolSchema>;
export type Application = z.infer<typeof applicationSchema>;
