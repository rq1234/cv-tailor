/**
 * Tests for pure utility functions in components/review/types.ts.
 * No React/DOM needed — plain TypeScript.
 */

import { describe, it, expect } from "vitest";
import {
  bulletText,
  bulletHasPlaceholder,
  bulletOutcomeType,
  getDiffMeta,
  sortByDateDesc,
  type TailoredBullet,
  type ExperienceDiff,
  type TailorResult,
} from "../components/review/types";

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeResult(overrides: Partial<TailorResult> = {}): TailorResult {
  return {
    cv_version_id: "cv-1",
    application_id: "app-1",
    diff_json: {},
    experience_meta: {},
    project_meta: {},
    activity_meta: {},
    education_data: [],
    skills_data: {},
    status: "review",
    ...overrides,
  };
}

function makeDiff(type?: "experience" | "project" | "activity"): ExperienceDiff {
  return {
    type,
    original_bullets: ["Original bullet"],
    suggested_bullets: ["Suggested bullet"],
    changes_made: [],
    confidence: 0.9,
  };
}

// ── bulletText ────────────────────────────────────────────────────────────────

describe("bulletText", () => {
  it("returns string bullet as-is", () => {
    expect(bulletText("Plain string bullet")).toBe("Plain string bullet");
  });

  it("extracts text from TailoredBullet object", () => {
    const bullet: TailoredBullet = {
      text: "Improved throughput by 30%",
      has_placeholder: false,
      outcome_type: "quantified",
    };
    expect(bulletText(bullet)).toBe("Improved throughput by 30%");
  });

  it("handles empty string bullet", () => {
    expect(bulletText("")).toBe("");
  });

  it("handles TailoredBullet with empty text", () => {
    const bullet: TailoredBullet = { text: "", has_placeholder: false, outcome_type: "" };
    expect(bulletText(bullet)).toBe("");
  });
});

// ── bulletHasPlaceholder ──────────────────────────────────────────────────────

describe("bulletHasPlaceholder", () => {
  it("returns false for plain string without [X]", () => {
    expect(bulletHasPlaceholder("Reduced latency by 40%")).toBe(false);
  });

  it("returns true for plain string containing [X]", () => {
    expect(bulletHasPlaceholder("Improved throughput by [X]%")).toBe(true);
  });

  it("returns TailoredBullet.has_placeholder when true", () => {
    const bullet: TailoredBullet = { text: "foo", has_placeholder: true, outcome_type: "" };
    expect(bulletHasPlaceholder(bullet)).toBe(true);
  });

  it("returns TailoredBullet.has_placeholder when false", () => {
    const bullet: TailoredBullet = { text: "foo", has_placeholder: false, outcome_type: "" };
    expect(bulletHasPlaceholder(bullet)).toBe(false);
  });

  it("does not check string content of TailoredBullet for [X]", () => {
    // TailoredBullet.has_placeholder=false overrides even if text contains [X]
    const bullet: TailoredBullet = {
      text: "Improved by [X]%",
      has_placeholder: false,
      outcome_type: "",
    };
    expect(bulletHasPlaceholder(bullet)).toBe(false);
  });
});

// ── bulletOutcomeType ─────────────────────────────────────────────────────────

describe("bulletOutcomeType", () => {
  it("returns empty string for plain string bullet", () => {
    expect(bulletOutcomeType("some bullet text")).toBe("");
  });

  it("returns outcome_type from TailoredBullet", () => {
    const bullet: TailoredBullet = {
      text: "foo",
      has_placeholder: false,
      outcome_type: "quantified",
    };
    expect(bulletOutcomeType(bullet)).toBe("quantified");
  });

  it("returns empty string for TailoredBullet with empty outcome_type", () => {
    const bullet: TailoredBullet = { text: "foo", has_placeholder: false, outcome_type: "" };
    expect(bulletOutcomeType(bullet)).toBe("");
  });
});

// ── getDiffMeta ───────────────────────────────────────────────────────────────

describe("getDiffMeta", () => {
  describe("experience (default)", () => {
    it("returns experience meta for undefined type", () => {
      const result = makeResult({
        experience_meta: {
          "exp-1": {
            company: "Acme Corp",
            role_title: "Backend Engineer",
            date_start: "2022-01-01",
            date_end: "2023-06-01",
            is_current: false,
          },
        },
      });
      const meta = getDiffMeta("exp-1", makeDiff(), result);
      expect(meta.isProject).toBe(false);
      expect(meta.isActivity).toBe(false);
      expect(meta.title).toBe("Backend Engineer");
      expect(meta.subtitle).toBe("Acme Corp");
      expect(meta.sectionLabel).toBe("Experience");
      expect(meta.dateRange).toContain("2022-01-01");
      expect(meta.dateRange).toContain("2023-06-01");
    });

    it("shows Present for current role", () => {
      const result = makeResult({
        experience_meta: {
          "exp-1": {
            company: "TechCo",
            role_title: "Engineer",
            date_start: "2023-01-01",
            date_end: null,
            is_current: true,
          },
        },
      });
      const meta = getDiffMeta("exp-1", makeDiff("experience"), result);
      expect(meta.dateRange).toContain("Present");
    });

    it("falls back gracefully when meta is missing", () => {
      const result = makeResult();
      const meta = getDiffMeta("missing-id", makeDiff("experience"), result);
      expect(meta.title).toBe("Unknown Role");
      expect(meta.subtitle).toBe("");
      expect(meta.dateRange).toBe("");
    });
  });

  describe("project", () => {
    it("returns project meta", () => {
      const result = makeResult({
        project_meta: {
          "proj-1": {
            name: "CV Tailor",
            description: "AI-powered resume tool",
            date_start: "2024-01-01",
            date_end: "2024-06-01",
          },
        },
      });
      const meta = getDiffMeta("proj-1", makeDiff("project"), result);
      expect(meta.isProject).toBe(true);
      expect(meta.isActivity).toBe(false);
      expect(meta.title).toBe("CV Tailor");
      expect(meta.subtitle).toBe("AI-powered resume tool");
      expect(meta.sectionLabel).toBe("Project");
      expect(meta.dateRange).toContain("2024-01-01");
    });

    it("falls back gracefully for unknown project", () => {
      const result = makeResult();
      const meta = getDiffMeta("unknown", makeDiff("project"), result);
      expect(meta.title).toBe("Unknown Project");
      expect(meta.sectionLabel).toBe("Project");
    });
  });

  describe("activity", () => {
    it("returns activity meta", () => {
      const result = makeResult({
        activity_meta: {
          "act-1": {
            organization: "Tech Society",
            role_title: "VP",
            date_start: "2021-09-01",
            date_end: null,
            is_current: true,
          },
        },
      });
      const meta = getDiffMeta("act-1", makeDiff("activity"), result);
      expect(meta.isActivity).toBe(true);
      expect(meta.isProject).toBe(false);
      expect(meta.title).toBe("VP");
      expect(meta.subtitle).toBe("Tech Society");
      expect(meta.sectionLabel).toBe("Activity");
      expect(meta.dateRange).toContain("Present");
    });

    it("falls back gracefully for unknown activity", () => {
      const result = makeResult();
      const meta = getDiffMeta("unknown", makeDiff("activity"), result);
      expect(meta.title).toBe("Unknown Role");
      expect(meta.sectionLabel).toBe("Activity");
    });
  });
});

// ── sortByDateDesc ────────────────────────────────────────────────────────────

describe("sortByDateDesc", () => {
  it("sorts experiences by date_start descending", () => {
    const result = makeResult({
      experience_meta: {
        "exp-old": {
          company: "Old Co",
          role_title: "Analyst",
          date_start: "2019-01-01",
          date_end: "2021-01-01",
          is_current: false,
        },
        "exp-new": {
          company: "New Co",
          role_title: "Engineer",
          date_start: "2022-01-01",
          date_end: null,
          is_current: true,
        },
      },
    });
    const entries: [string, ExperienceDiff][] = [
      ["exp-old", makeDiff("experience")],
      ["exp-new", makeDiff("experience")],
    ];
    const sorted = sortByDateDesc(entries, result);
    expect(sorted[0][0]).toBe("exp-new");
    expect(sorted[1][0]).toBe("exp-old");
  });

  it("puts null date_start entries last", () => {
    const result = makeResult({
      experience_meta: {
        "exp-dated": {
          company: "Co",
          role_title: "Role",
          date_start: "2020-01-01",
          date_end: null,
          is_current: false,
        },
        "exp-nodated": {
          company: "Co2",
          role_title: "Role2",
          date_start: null,
          date_end: null,
          is_current: false,
        },
      },
    });
    const entries: [string, ExperienceDiff][] = [
      ["exp-nodated", makeDiff("experience")],
      ["exp-dated", makeDiff("experience")],
    ];
    const sorted = sortByDateDesc(entries, result);
    expect(sorted[0][0]).toBe("exp-dated");
    expect(sorted[1][0]).toBe("exp-nodated");
  });

  it("handles all null dates without error", () => {
    const result = makeResult({
      experience_meta: {
        "a": { company: "A", role_title: "Role A", date_start: null, date_end: null, is_current: false },
        "b": { company: "B", role_title: "Role B", date_start: null, date_end: null, is_current: false },
      },
    });
    const entries: [string, ExperienceDiff][] = [
      ["a", makeDiff()],
      ["b", makeDiff()],
    ];
    expect(() => sortByDateDesc(entries, result)).not.toThrow();
  });

  it("returns empty array for empty input", () => {
    const result = makeResult();
    expect(sortByDateDesc([], result)).toEqual([]);
  });

  it("works with mixed experience/project meta", () => {
    const result = makeResult({
      project_meta: {
        "proj-1": { name: "P1", description: null, date_start: "2023-06-01", date_end: null },
      },
      experience_meta: {
        "exp-1": { company: "C", role_title: "R", date_start: "2021-01-01", date_end: null, is_current: false },
      },
    });
    const entries: [string, ExperienceDiff][] = [
      ["exp-1", makeDiff("experience")],
      ["proj-1", makeDiff("project")],
    ];
    const sorted = sortByDateDesc(entries, result);
    expect(sorted[0][0]).toBe("proj-1");
    expect(sorted[1][0]).toBe("exp-1");
  });
});
