"use client";

import { useEffect, useState } from "react";
import { useExperiencePool } from "@/hooks/useExperiencePool";
import { api } from "@/lib/api";
import Link from "next/link";
import ExperienceCard from "@/components/library/ExperienceCard";
import { Spinner } from "@/components/ui/Skeleton";

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
  const { pool, poolLoading, poolError, fetchPool } = useExperiencePool();
  const [reclassifying, setReclassifying] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [opError, setOpError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [editingEduId, setEditingEduId] = useState<string | null>(null);
  const [eduAchievements, setEduAchievements] = useState<string>("");
  const [savingEdu, setSavingEdu] = useState(false);

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
    setOpError(null);
    try {
      await api.post("/api/experiences/reclassify", { experience_ids: [expId] });
      await fetchPool();
    } catch (err) {
      setOpError(err instanceof Error ? err.message : "Failed to move to activities");
    } finally {
      setReclassifying(null);
    }
  };

  const handleDelete = async (endpoint: string, id: string) => {
    setDeleting(id);
    setOpError(null);
    try {
      await api.delete(`${endpoint}/${id}`);
      await fetchPool();
    } catch (err) {
      setOpError(err instanceof Error ? err.message : "Failed to delete item");
    } finally {
      setDeleting(null);
    }
  };

  const handleSaveEduAchievements = async (id: string) => {
    setSavingEdu(true);
    setOpError(null);
    try {
      const achievements = eduAchievements.split("\n").map((s) => s.trim()).filter(Boolean);
      await api.put(`/api/experiences/education/${id}`, { achievements });
      await fetchPool();
      setEditingEduId(null);
    } catch (err) {
      setOpError(err instanceof Error ? err.message : "Failed to save achievements");
    } finally {
      setSavingEdu(false);
    }
  };

  const handleEditBullets = async (id: string, type: "work" | "project" | "activity", bullets: string[]) => {
    const endpoint =
      type === "work" ? `/api/experiences/${id}`
      : type === "project" ? `/api/experiences/projects/${id}`
      : `/api/experiences/activities/${id}`;
    await api.put(endpoint, { bullets });
    await fetchPool();
  };

  useEffect(() => {
    fetchPool({ silent: !!pool });
  }, [fetchPool]); // eslint-disable-line react-hooks/exhaustive-deps

  if (poolLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Spinner size="md" />
        <p className="text-sm text-muted-foreground">Loading experience pool...</p>
      </div>
    );
  }

  if (poolError) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <p className="text-sm font-medium text-red-600">Could not connect to backend</p>
        <p className="text-xs text-muted-foreground max-w-sm text-center">{poolError}</p>
        <button
          onClick={fetchPool}
          className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
        >
          Retry
        </button>
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

  const q = search.trim().toLowerCase();
  const filteredExpGroups = q ? expGroups.filter(({ primary: e }) =>
    (e.company ?? "").toLowerCase().includes(q) || (e.role_title ?? "").toLowerCase().includes(q)
  ) : expGroups;
  const filteredProjGroups = q ? projGroups.filter(({ primary: p }) =>
    (p.name ?? "").toLowerCase().includes(q) || (p.description ?? "").toLowerCase().includes(q)
  ) : projGroups;
  const filteredActGroups = q ? actGroups.filter(({ primary: a }) =>
    (a.organization ?? "").toLowerCase().includes(q) || (a.role_title ?? "").toLowerCase().includes(q)
  ) : actGroups;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-3xl font-black tracking-tight text-foreground">Experience Library</h1>
        <div className="flex items-center gap-2">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search experiences…"
            className="w-full sm:w-56 rounded-lg border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-150"
          />
          <Link
            href="/upload"
            className="shrink-0 inline-flex items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Add / Update CV
          </Link>
        </div>
      </div>

      {opError && (
        <div className="flex items-center justify-between rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <span>{opError}</span>
          <button onClick={() => setOpError(null)} className="ml-2 text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

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
          {filteredExpGroups.length > 0 && (
            <section>
              <h2 className="text-[11px] font-black uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-3">
                <span>Work Experience</span>
                <span className="flex-1 h-px bg-border" />
                <span className="font-medium normal-case tracking-normal text-muted-foreground/60">{filteredExpGroups.length} roles</span>
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredExpGroups.map(({ primary: exp, variants }) => (
                  <ExperienceCard
                    key={exp.id}
                    primary={exp}
                    variants={variants}
                    expanded={expandedGroups.has(exp.id)}
                    onToggle={() => toggleGroup(exp.id)}
                    nameField="company"
                    onDelete={(id) => handleDelete("/api/experiences", id)}
                    deleting={deleting}
                    onEditBullets={(id, bullets) => handleEditBullets(id, "work", bullets)}
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
              <h2 className="text-[11px] font-black uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-3">
                <span>Education</span>
                <span className="flex-1 h-px bg-border" />
                <span className="font-medium normal-case tracking-normal text-muted-foreground/60">{eduGroups.length}</span>
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {eduGroups.map(({ primary: edu, variants }) => (
                  <div key={edu.id} className="rounded-xl border border-border bg-card p-4 hover:-translate-y-px hover:shadow-md hover:shadow-black/5 transition-all duration-200">
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-bold tracking-tight">{edu.degree || "Untitled"}</h3>
                        <p className="text-sm font-medium text-muted-foreground">{edu.institution || "Unknown Institution"}</p>
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
                          onClick={() => {
                            const existing = (edu as { achievements?: string[] }).achievements ?? [];
                            setEduAchievements(existing.join("\n"));
                            setEditingEduId(edu.id);
                          }}
                          className="inline-flex items-center rounded-full px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                          title="Edit achievements"
                        >
                          Edit
                        </button>
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
                    {editingEduId === edu.id && (
                      <div className="mt-3 border-t pt-3 space-y-2">
                        <p className="text-xs font-medium text-slate-600">Achievements (one per line)</p>
                        <textarea
                          value={eduAchievements}
                          onChange={(e) => setEduAchievements(e.target.value)}
                          rows={4}
                          placeholder="e.g. Awarded First Class Honours&#10;Relevant modules: Machine Learning, Algorithms"
                          className="w-full rounded border px-2 py-1.5 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                        <div className="flex gap-1.5">
                          <button
                            onClick={() => handleSaveEduAchievements(edu.id)}
                            disabled={savingEdu}
                            className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground disabled:opacity-50"
                          >
                            {savingEdu ? "Saving…" : "Save"}
                          </button>
                          <button
                            onClick={() => setEditingEduId(null)}
                            className="rounded-md border px-3 py-1 text-xs hover:bg-muted"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
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
          {filteredProjGroups.length > 0 && (
            <section>
              <h2 className="text-[11px] font-black uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-3">
                <span>Projects</span>
                <span className="flex-1 h-px bg-border" />
                <span className="font-medium normal-case tracking-normal text-muted-foreground/60">{filteredProjGroups.length}</span>
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredProjGroups.map(({ primary: proj, variants }) => (
                  <div key={proj.id} className="rounded-xl border border-border bg-card p-4 hover:-translate-y-px hover:shadow-md hover:shadow-black/5 transition-all duration-200">
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-bold tracking-tight">{proj.name || "Untitled Project"}</h3>
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
                          <span key={tag} className="inline-flex items-center rounded-full bg-primary/8 px-2.5 py-0.5 text-xs font-medium text-primary">
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
                                    <span key={tag} className="inline-flex items-center rounded-full bg-primary/8 px-1.5 py-0.5 text-[10px] font-medium text-primary">
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
          {filteredActGroups.length > 0 && (
            <section>
              <h2 className="text-[11px] font-black uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-3">
                <span>Activities</span>
                <span className="flex-1 h-px bg-border" />
                <span className="font-medium normal-case tracking-normal text-muted-foreground/60">{filteredActGroups.length}</span>
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredActGroups.map(({ primary: act, variants }) => (
                  <ExperienceCard
                    key={act.id}
                    primary={act}
                    variants={variants}
                    expanded={expandedGroups.has(act.id)}
                    onToggle={() => toggleGroup(act.id)}
                    nameField="organization"
                    onDelete={(id) => handleDelete("/api/experiences/activities", id)}
                    deleting={deleting}
                    onEditBullets={(id, bullets) => handleEditBullets(id, "activity", bullets)}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Skills */}
          {pool!.skills.length > 0 && (
            <section>
              <h2 className="text-[11px] font-black uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-3">
                <span>Skills</span>
                <span className="flex-1 h-px bg-border" />
                <span className="font-medium normal-case tracking-normal text-muted-foreground/60">{pool!.skills.length}</span>
              </h2>
              <div className="flex flex-wrap gap-2">
                {pool!.skills.map((skill) => (
                  <span key={skill.id} className="inline-flex items-center rounded-full border border-border bg-card px-3 py-1 text-sm font-medium hover:bg-muted hover:border-primary/30 transition-all duration-150 group">
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
