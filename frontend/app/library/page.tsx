"use client";

import { useEffect, useState } from "react";
import { useExperiencePool } from "@/hooks/useExperiencePool";
import { api } from "@/lib/api";
import Link from "next/link";
import ExperienceCard from "@/components/library/ExperienceCard";

/** Group items by variant_group_id. Primary variant shown first; others are collapsible. */
function groupByVariant<T extends { id: string; variant_group_id?: string | null; is_primary_variant?: boolean }>(
  items: T[]
): { primary: T; variants: T[] }[] {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const key = item.variant_group_id || item.id;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  return Array.from(groups.values()).map((group) => {
    const primary = group.find((g) => g.is_primary_variant) || group[0];
    const variants = group.filter((g) => g.id !== primary.id);
    return { primary, variants };
  });
}

/** Same grouping for education (uses institution+degree as key since no variant_group_id). */
function groupEducation<T extends { id: string; institution?: string | null; degree?: string | null }>(
  items: T[]
): { primary: T; variants: T[] }[] {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const key = `${(item.institution || "").toLowerCase()}|${(item.degree || "").toLowerCase()}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  return Array.from(groups.values()).map((group) => ({
    primary: group[0],
    variants: group.slice(1),
  }));
}

export default function LibraryPage() {
  const { pool, poolLoading, fetchPool } = useExperiencePool();
  const [reclassifying, setReclassifying] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const toggleGroup = (id: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleMoveToActivities = async (expId: string) => {
    setReclassifying(expId);
    try {
      await api.post("/api/experiences/reclassify", { experience_ids: [expId] });
      await fetchPool();
    } catch {
      // silently fail
    } finally {
      setReclassifying(null);
    }
  };

  const handleDelete = async (endpoint: string, id: string) => {
    setDeleting(id);
    try {
      await api.delete(`${endpoint}/${id}`);
      await fetchPool();
    } catch {
      // silently fail
    } finally {
      setDeleting(null);
    }
  };

  useEffect(() => {
    fetchPool();
  }, [fetchPool]);

  if (poolLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">Loading experience pool...</p>
      </div>
    );
  }

  const hasContent =
    pool &&
    (pool.work_experiences.length > 0 ||
      pool.education.length > 0 ||
      pool.projects.length > 0 ||
      pool.activities.length > 0 ||
      pool.skills.length > 0);

  const expGroups = pool ? groupByVariant(pool.work_experiences) : [];
  const eduGroups = pool ? groupEducation(pool.education) : [];
  const projGroups = pool ? groupByVariant(pool.projects) : [];
  const actGroups = pool ? groupByVariant(pool.activities) : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Experience Library</h1>
        <Link
          href="/upload"
          className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Upload CV
        </Link>
      </div>

      {!hasContent ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12">
          <p className="text-lg text-muted-foreground mb-4">Your experience pool is empty</p>
          <p className="text-sm text-muted-foreground mb-6">
            Upload a CV to get started. Your experiences, education, and skills will be extracted and stored here.
          </p>
          <Link
            href="/upload"
            className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Upload your first CV
          </Link>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Work Experiences */}
          {expGroups.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3">
                Work Experience ({expGroups.length} roles, {pool!.work_experiences.length} variants)
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {expGroups.map(({ primary: exp, variants }) => (
                  <ExperienceCard
                    key={exp.id}
                    primary={exp}
                    variants={variants}
                    expanded={expandedGroups.has(exp.id)}
                    onToggle={() => toggleGroup(exp.id)}
                    nameField="company"
                    onDelete={(id) => handleDelete("/api/experiences", id)}
                    deleting={deleting}
                    actions={
                      <button
                        onClick={() => handleMoveToActivities(exp.id)}
                        disabled={reclassifying === exp.id}
                        className="mt-2 text-xs text-muted-foreground hover:text-foreground underline disabled:opacity-50"
                      >
                        {reclassifying === exp.id ? "Moving..." : "Move to Activities"}
                      </button>
                    }
                  />
                ))}
              </div>
            </section>
          )}

          {/* Education */}
          {eduGroups.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3">Education ({eduGroups.length})</h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {eduGroups.map(({ primary: edu, variants }) => (
                  <div key={edu.id} className="rounded-lg border p-4 hover:shadow-sm transition-shadow">
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-medium">{edu.degree || "Untitled"}</h3>
                        <p className="text-sm text-muted-foreground">{edu.institution || "Unknown Institution"}</p>
                      </div>
                      <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
                        {variants.length > 0 && (
                          <button
                            onClick={() => toggleGroup(edu.id)}
                            className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground hover:bg-muted/80"
                          >
                            {variants.length + 1} variants
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete("/api/experiences/education", edu.id)}
                          disabled={deleting === edu.id}
                          className="inline-flex items-center rounded-full px-1.5 py-0.5 text-xs text-red-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                          title="Delete"
                        >
                          {deleting === edu.id ? "..." : "✕"}
                        </button>
                      </div>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {edu.date_start || "?"} - {edu.date_end || "?"}
                    </p>
                    {expandedGroups.has(edu.id) && variants.length > 0 && (
                      <div className="mt-3 border-t pt-2 space-y-2">
                        {variants.map((v) => (
                          <div key={v.id} className="rounded bg-muted/50 p-2 text-sm flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              <span className="font-medium">{v.degree || "Untitled"}</span>
                              <span className="text-muted-foreground"> &mdash; {v.institution || "Unknown"}</span>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {v.date_start || "?"} - {v.date_end || "?"}
                              </p>
                            </div>
                            <button
                              onClick={() => handleDelete("/api/experiences/education", v.id)}
                              disabled={deleting === v.id}
                              className="flex-shrink-0 inline-flex items-center rounded-full px-1.5 py-0.5 text-xs text-red-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                              title="Delete"
                            >
                              {deleting === v.id ? "..." : "✕"}
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Projects */}
          {projGroups.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3">
                Projects ({projGroups.length}{pool!.projects.length > projGroups.length ? ` projects, ${pool!.projects.length} variants` : ""})
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {projGroups.map(({ primary: proj, variants }) => (
                  <div key={proj.id} className="rounded-lg border p-4 hover:shadow-sm transition-shadow">
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-medium">{proj.name || "Untitled Project"}</h3>
                        {proj.description && (
                          <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{proj.description}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
                        {variants.length > 0 && (
                          <button
                            onClick={() => toggleGroup(proj.id)}
                            className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground hover:bg-muted/80"
                          >
                            {variants.length + 1} variants
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete("/api/experiences/projects", proj.id)}
                          disabled={deleting === proj.id}
                          className="inline-flex items-center rounded-full px-1.5 py-0.5 text-xs text-red-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                          title="Delete"
                        >
                          {deleting === proj.id ? "..." : "✕"}
                        </button>
                      </div>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {proj.date_start || "?"} - {proj.date_end || "?"}
                    </p>
                    {proj.domain_tags && proj.domain_tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {proj.domain_tags.map((tag: string) => (
                          <span key={tag} className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                    {expandedGroups.has(proj.id) && variants.length > 0 && (
                      <div className="mt-3 border-t pt-2 space-y-2">
                        {variants.map((v) => (
                          <div key={v.id} className="rounded bg-muted/50 p-2 text-sm flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              <span className="font-medium">{v.name || "Untitled"}</span>
                              {v.description && (
                                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{v.description}</p>
                              )}
                              {v.domain_tags && v.domain_tags.length > 0 && (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {v.domain_tags.map((tag: string) => (
                                    <span key={tag} className="inline-flex items-center rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700">
                                      {tag}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                            <button
                              onClick={() => handleDelete("/api/experiences/projects", v.id)}
                              disabled={deleting === v.id}
                              className="flex-shrink-0 inline-flex items-center rounded-full px-1.5 py-0.5 text-xs text-red-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                              title="Delete"
                            >
                              {deleting === v.id ? "..." : "✕"}
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Activities */}
          {actGroups.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3">
                Activities ({actGroups.length}{pool!.activities.length > actGroups.length ? ` roles, ${pool!.activities.length} variants` : ""})
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {actGroups.map(({ primary: act, variants }) => (
                  <ExperienceCard
                    key={act.id}
                    primary={act}
                    variants={variants}
                    expanded={expandedGroups.has(act.id)}
                    onToggle={() => toggleGroup(act.id)}
                    nameField="organization"
                    onDelete={(id) => handleDelete("/api/experiences/activities", id)}
                    deleting={deleting}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Skills */}
          {pool!.skills.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3">Skills ({pool!.skills.length})</h2>
              <div className="flex flex-wrap gap-2">
                {pool!.skills.map((skill) => (
                  <span key={skill.id} className="inline-flex items-center rounded-full border px-3 py-1 text-sm group">
                    {skill.name}
                    {skill.category && (
                      <span className="ml-1.5 text-xs text-muted-foreground">({skill.category})</span>
                    )}
                    <button
                      onClick={() => handleDelete("/api/experiences/skills", skill.id)}
                      disabled={deleting === skill.id}
                      className="ml-1.5 inline-flex items-center text-xs text-red-400 hover:text-red-600 disabled:opacity-50"
                      title="Delete"
                    >
                      {deleting === skill.id ? "..." : "✕"}
                    </button>
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
