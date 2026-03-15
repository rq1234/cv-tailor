import { Briefcase, CalendarCheck, Trophy } from "lucide-react";
import type { AppStats } from "@/hooks/useApplicationsList";

const STAT_CARDS = [
  {
    key: "total",
    label: "Total",
    icon: Briefcase,
    iconClass: "text-blue-600 bg-blue-50",
    valueClass: "text-blue-700",
  },
  {
    key: "interview",
    label: "Interview Rate",
    icon: CalendarCheck,
    iconClass: "text-violet-600 bg-violet-50",
    valueClass: "text-violet-700",
  },
  {
    key: "offer",
    label: "Offer Rate",
    icon: Trophy,
    iconClass: "text-emerald-600 bg-emerald-50",
    valueClass: "text-emerald-700",
  },
] as const;

export default function ApplicationStats({ stats }: { stats: AppStats }) {
  const interviewRate =
    stats.total > 0
      ? `${Math.round(((stats.by_outcome.interview ?? 0) + (stats.by_outcome.offer ?? 0)) / stats.total * 100)}%`
      : "—";
  const offerRate =
    stats.total > 0
      ? `${Math.round((stats.by_outcome.offer ?? 0) / stats.total * 100)}%`
      : "—";

  const values: Record<string, string | number> = {
    total: stats.total,
    interview: interviewRate,
    offer: offerRate,
  };

  const maxInterviewRate = stats.by_domain.length > 0
    ? Math.max(...stats.by_domain.map((d) => d.interview_rate), 0.01)
    : 1;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {STAT_CARDS.map(({ key, label, icon: Icon, iconClass, valueClass }) => (
          <div
            key={key}
            className="rounded-xl border bg-white px-4 py-4 shadow-sm hover:shadow-md transition-shadow"
          >
            <div className={`mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg ${iconClass}`}>
              <Icon className="h-4 w-4" />
            </div>
            <div className={`text-2xl font-bold ${valueClass}`}>{values[key]}</div>
            <div className="text-xs text-slate-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {stats.by_domain.length > 1 && (
        <div className="rounded-xl border bg-white px-4 py-4 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">By domain</div>
          <div className="space-y-2.5">
            {stats.by_domain.map((d) => (
              <div key={d.domain} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="capitalize font-medium text-slate-700">{d.domain}</span>
                  <div className="flex gap-3 text-slate-500">
                    <span>{d.count} app{d.count !== 1 ? "s" : ""}</span>
                    <span className="text-violet-600 font-medium">{Math.round(d.interview_rate * 100)}% interview</span>
                  </div>
                </div>
                <div className="h-1.5 w-full rounded-full bg-slate-100">
                  <div
                    className="h-1.5 rounded-full bg-violet-400 transition-all"
                    style={{ width: `${Math.round((d.interview_rate / maxInterviewRate) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
