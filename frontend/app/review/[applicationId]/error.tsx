"use client";

export default function ReviewError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
      <p className="text-lg font-semibold text-destructive">Failed to load review</p>
      <p className="text-sm text-muted-foreground max-w-sm">
        {error.message || "An unexpected error occurred while loading your CV review."}
      </p>
      <button
        onClick={reset}
        className="rounded-md border px-4 py-2 text-sm hover:bg-muted"
      >
        Try again
      </button>
    </div>
  );
}
