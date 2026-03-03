import { useState } from "react";

interface VariantItem {
  id: string;
  role_title?: string | null;
  company?: string | null;
  organization?: string | null;
  date_start?: string | null;
  date_end?: string | null;
  is_current?: boolean;
  domain_tags?: string[] | null;
  needs_review?: boolean;
  variant_group_id?: string | null;
  is_primary_variant?: boolean;
  bullets?: unknown[] | null;
}

interface ExperienceCardProps<T extends VariantItem> {
  primary: T;
  variants: T[];
  expanded: boolean;
  onToggle: () => void;
  nameField: "company" | "organization";
  actions?: React.ReactNode;
  onDelete?: (id: string) => void;
  deleting?: string | null;
  onEditBullets?: (id: string, bullets: string[]) => Promise<void>;
}

function extractBulletStrings(raw: unknown[] | null | undefined): string[] {
  if (!raw || !Array.isArray(raw)) return [];
  return raw.map((b) => {
    if (typeof b === "string") return b;
    if (b && typeof b === "object" && "text" in b) return String((b as { text: unknown }).text);
    return String(b);
  }).filter(Boolean);
}

function BulletList({
  id,
  bullets,
  onEditBullets,
}: {
  id: string;
  bullets: string[];
  onEditBullets?: (id: string, bullets: string[]) => Promise<void>;
}) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);

  if (bullets.length === 0) return null;

  const handleEdit = (idx: number) => {
    setEditingIndex(idx);
    setEditValue(bullets[idx]);
  };

  const handleSave = async (idx: number) => {
    if (!onEditBullets || editValue.trim() === bullets[idx]) {
      setEditingIndex(null);
      return;
    }
    const updated = bullets.map((b, i) => (i === idx ? editValue.trim() : b));
    setSaving(true);
    try {
      await onEditBullets(id, updated);
    } finally {
      setSaving(false);
      setEditingIndex(null);
    }
  };

  return (
    <div className="mt-2 space-y-1">
      {bullets.map((bullet, idx) => (
        <div key={idx} className="group flex items-start gap-1.5 text-xs text-slate-600">
          <span className="mt-0.5 flex-shrink-0 text-slate-400">•</span>
          {editingIndex === idx ? (
            <div className="flex-1 flex flex-col gap-1">
              <textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                className="w-full rounded border px-2 py-1 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
                rows={2}
                autoFocus
              />
              <div className="flex gap-1.5">
                <button
                  onClick={() => handleSave(idx)}
                  disabled={saving}
                  className="rounded bg-blue-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
                <button
                  onClick={() => setEditingIndex(null)}
                  className="rounded border px-2 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-start justify-between gap-1">
              <span>{bullet}</span>
              {onEditBullets && (
                <button
                  onClick={() => handleEdit(idx)}
                  className="flex-shrink-0 opacity-0 group-hover:opacity-100 rounded px-1 py-0.5 text-[10px] text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-opacity"
                  title="Edit bullet"
                >
                  ✎
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function ExperienceCard<T extends VariantItem>({
  primary,
  variants,
  expanded,
  onToggle,
  nameField,
  actions,
  onDelete,
  deleting,
  onEditBullets,
}: ExperienceCardProps<T>) {
  const [bulletsExpanded, setBulletsExpanded] = useState(false);
  const subtitle = nameField === "company" ? primary.company : primary.organization;
  const variantSubtitle = (v: T) => nameField === "company" ? v.company : v.organization;
  const bullets = extractBulletStrings(primary.bullets);

  return (
    <div className="rounded-lg border p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="font-medium">{primary.role_title || "Untitled Role"}</h3>
          <p className="text-sm text-muted-foreground">
            {subtitle || (nameField === "company" ? "Unknown Company" : "Unknown Organization")}
          </p>
        </div>
        <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
          {variants.length > 0 && (
            <button
              onClick={onToggle}
              className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground hover:bg-muted/80"
            >
              {variants.length + 1} variants
            </button>
          )}
          {primary.needs_review && (
            <span className="inline-flex items-center rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-medium text-yellow-800">
              Needs review
            </span>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(primary.id)}
              disabled={deleting === primary.id}
              className="inline-flex items-center rounded-full px-1.5 py-0.5 text-xs text-red-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
              title="Delete"
            >
              {deleting === primary.id ? "..." : "✕"}
            </button>
          )}
        </div>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {primary.date_start || "?"} - {primary.is_current ? "Present" : primary.date_end || "?"}
      </p>
      {primary.domain_tags && primary.domain_tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {primary.domain_tags.map((tag) => (
            <span key={tag} className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Bullet list with inline editing */}
      {bullets.length > 0 && (
        <div className="mt-2">
          <button
            onClick={() => setBulletsExpanded((v) => !v)}
            className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
          >
            {bulletsExpanded ? "▾ Hide bullets" : `▸ ${bullets.length} bullet${bullets.length !== 1 ? "s" : ""}`}
          </button>
          {bulletsExpanded && (
            <BulletList id={primary.id} bullets={bullets} onEditBullets={onEditBullets} />
          )}
        </div>
      )}

      {actions}
      {expanded && variants.length > 0 && (
        <div className="mt-3 border-t pt-2 space-y-2">
          {variants.map((v) => (
            <div key={v.id} className="rounded bg-muted/50 p-2 text-sm flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <span className="font-medium">{v.role_title}</span>
                <span className="text-muted-foreground"> &mdash; {variantSubtitle(v)}</span>
                {v.domain_tags && v.domain_tags.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {v.domain_tags.map((tag) => (
                      <span key={tag} className="inline-flex items-center rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-700">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {onDelete && (
                <button
                  onClick={() => onDelete(v.id)}
                  disabled={deleting === v.id}
                  className="flex-shrink-0 inline-flex items-center rounded-full px-1.5 py-0.5 text-xs text-red-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                  title="Delete"
                >
                  {deleting === v.id ? "..." : "✕"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
