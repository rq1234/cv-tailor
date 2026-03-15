import Link from "next/link";
import { OUTCOME_OPTIONS, type Application } from "@/lib/schemas";
import { STATUS_LABEL } from "@/lib/constants";

const KANBAN_COLUMNS: { key: string | null; label: string; headerClass: string }[] = [
  { key: null,         label: "Untracked",   headerClass: "border-slate-200 bg-slate-50 text-slate-600" },
  { key: "applied",    label: "Applied",     headerClass: "border-blue-200 bg-blue-50 text-blue-700" },
  { key: "interview",  label: "Interviewing", headerClass: "border-purple-200 bg-purple-50 text-purple-700" },
  { key: "offer",      label: "Offer",       headerClass: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  { key: "rejected",   label: "Rejected",    headerClass: "border-red-200 bg-red-50 text-red-600" },
  { key: "withdrawn",  label: "Withdrawn",   headerClass: "border-gray-200 bg-gray-50 text-gray-600" },
];

interface ApplicationKanbanProps {
  applications: Application[];
}

export default function ApplicationKanban({ applications }: ApplicationKanbanProps) {
  const grouped = new Map<string | null, Application[]>();
  for (const col of KANBAN_COLUMNS) grouped.set(col.key, []);
  for (const app of applications) {
    const key = app.outcome ?? null;
    if (grouped.has(key)) grouped.get(key)!.push(app);
    else grouped.get(null)!.push(app);
  }

  // Only render columns that have apps, except we always show Applied, Interviewing, Offer
  const ALWAYS_SHOW = new Set(["applied", "interview", "offer"]);
  const visibleColumns = KANBAN_COLUMNS.filter(
    (col) => ALWAYS_SHOW.has(col.key ?? "") || (grouped.get(col.key)?.length ?? 0) > 0
  );

  return (
    <div className="overflow-x-auto pb-4">
      <div className="flex gap-4" style={{ minWidth: `${visibleColumns.length * 240}px` }}>
        {visibleColumns.map((col) => {
          const colApps = grouped.get(col.key) ?? [];
          return (
            <div key={String(col.key)} className="flex-1 min-w-[220px] max-w-xs flex flex-col gap-2">
              {/* Column header */}
              <div className={`flex items-center justify-between rounded-lg border px-3 py-2 ${col.headerClass}`}>
                <span className="text-xs font-semibold">{col.label}</span>
                <span className="text-xs font-medium opacity-70">{colApps.length}</span>
              </div>

              {/* Cards */}
              <div className="flex flex-col gap-2">
                {colApps.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-slate-200 px-3 py-4 text-center text-xs text-slate-400">
                    No applications
                  </div>
                ) : (
                  colApps.map((app) => {
                    const statusInfo = STATUS_LABEL[app.status] ?? { label: app.status, className: "bg-slate-100 text-slate-500" };
                    const isReviewable = app.status === "review" || app.status === "complete";
                    return (
                      <div
                        key={app.id}
                        className="rounded-lg border bg-white p-3 shadow-sm hover:shadow-md transition-shadow"
                      >
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-slate-800 truncate">{app.company_name}</p>
                            {app.role_title && (
                              <p className="text-xs text-slate-500 truncate">{app.role_title}</p>
                            )}
                          </div>
                          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${statusInfo.className}`}>
                            {statusInfo.label}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 mb-2">
                          {new Date(app.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        </p>
                        {isReviewable && (
                          <Link
                            href={`/review/${app.id}`}
                            className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-700 hover:bg-blue-100 transition-colors"
                          >
                            Review →
                          </Link>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
