// ── Spinner ──────────────────────────────────────────────────────────────────

const SPINNER_SIZE: Record<string, string> = {
  xs:  "h-3 w-3 border-2",
  sm:  "h-4 w-4 border-2",
  md:  "h-6 w-6 border-2",
  lg:  "h-8 w-8 border-4",
};

export function Spinner({ size = "md", className = "" }: { size?: "xs" | "sm" | "md" | "lg"; className?: string }) {
  return (
    <div
      className={`animate-spin rounded-full border-primary border-t-transparent ${SPINNER_SIZE[size]} ${className}`}
    />
  );
}

// ── ErrorBanner ───────────────────────────────────────────────────────────────

export function ErrorBanner({ message, className = "" }: { message: string; className?: string }) {
  return (
    <div className={`rounded-lg border border-red-200 bg-red-50 p-4 ${className}`}>
      <p className="text-sm text-red-700">{message}</p>
    </div>
  );
}

// ── Skeleton primitives ───────────────────────────────────────────────────────

function SkeletonLine({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-muted ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <SkeletonLine className="h-4 w-1/3" />
        <SkeletonLine className="h-5 w-16 rounded-full" />
      </div>
      <SkeletonLine className="h-3 w-1/2" />
      <SkeletonLine className="h-3 w-1/4" />
      <div className="flex gap-2 pt-1">
        <SkeletonLine className="h-7 w-16 rounded-md" />
        <SkeletonLine className="h-7 w-20 rounded-md" />
      </div>
    </div>
  );
}

export function SkeletonBulletCard() {
  return (
    <div className="rounded-lg border bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="border-b bg-slate-50 px-4 py-3 flex items-center gap-3">
        <SkeletonLine className="h-4 w-1/4" />
        <SkeletonLine className="h-3 w-1/6" />
      </div>
      {/* Two-column bullet row */}
      {[0, 1, 2].map((i) => (
        <div key={i} className="grid grid-cols-1 md:grid-cols-2 border-t">
          <div className="p-3 space-y-2 md:border-r">
            <SkeletonLine className="h-3 w-12" />
            <SkeletonLine className="h-3 w-full" />
            <SkeletonLine className="h-3 w-4/5" />
          </div>
          <div className="p-3 space-y-2">
            <div className="flex justify-between">
              <SkeletonLine className="h-3 w-16" />
              <div className="flex gap-1">
                <SkeletonLine className="h-6 w-16 rounded-md" />
                <SkeletonLine className="h-6 w-14 rounded-md" />
                <SkeletonLine className="h-6 w-12 rounded-md" />
              </div>
            </div>
            <SkeletonLine className="h-3 w-full" />
            <SkeletonLine className="h-3 w-3/5" />
          </div>
        </div>
      ))}
    </div>
  );
}
