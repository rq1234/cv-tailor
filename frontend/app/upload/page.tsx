"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CVDropzone } from "@/components/upload/CVDropzone";
import { api } from "@/lib/api";
import { parseSummarySchema, type ParseSummary, type ReviewItem, type UnclassifiedBlock } from "@/lib/schemas";
import { useAppStore } from "@/store/appStore";
import { OnboardingBanner } from "@/components/onboarding/OnboardingBanner";
import { Spinner } from "@/components/ui/Skeleton";

const CATEGORY_TO_API: Record<string, string> = {
  "Work Experience": "work_experience",
  "Education": "education",
  "Project": "project",
  "Activity": "activity",
  "Skill": "skill",
  "Ignore": "ignore",
};

export default function UploadPage() {
  const router = useRouter();
  const { setUploadResult } = useAppStore();
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ParseSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Editable state for review items
  const [reviewEdits, setReviewEdits] = useState<Record<string, string>>({});
  const [resolvedBlocks, setResolvedBlocks] = useState<Record<string, string>>({});

  const handleFileSelected = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const data = await api.upload<ParseSummary>("/api/cv/upload", file);
      const validated = parseSummarySchema.parse(data);
      setResult(validated);
      setUploadResult(validated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleReviewEdit = (itemId: string, value: string) => {
    setReviewEdits((prev) => ({ ...prev, [itemId]: value }));
  };

  const handleResolveBlock = (blockId: string, category: string) => {
    setResolvedBlocks((prev) => ({ ...prev, [blockId]: category }));
  };

  const allReviewItemsResolved =
    result &&
    result.needs_review.every((item: ReviewItem) => reviewEdits[item.id] !== undefined) &&
    result.unclassified_blocks.every((block: UnclassifiedBlock) => resolvedBlocks[block.id] !== undefined);

  const canSave =
    result &&
    (result.needs_review.length === 0 || allReviewItemsResolved) &&
    (result.unclassified_blocks.length === 0 ||
      result.unclassified_blocks.every((b: UnclassifiedBlock) => resolvedBlocks[b.id]));

  const handleSaveToLibrary = async () => {
    setError(null);
    try {
      // Resolve unclassified blocks
      await Promise.all(
        Object.entries(resolvedBlocks).map(([blockId, category]) => {
          const resolved_as = CATEGORY_TO_API[category] ?? "ignore";
          return api.post(`/api/experiences/${blockId}/resolve-unclassified?resolved_as=${resolved_as}`, {});
        })
      );

      // Send corrections for needs_review items (best-effort; silently skip unsupported tables)
      await Promise.all(
        result!.needs_review
          .filter((item: ReviewItem) => reviewEdits[item.id] !== undefined)
          .map((item: ReviewItem) => {
            const body = { [item.field]: reviewEdits[item.id] };
            if (item.table === "work_experiences") {
              return api.put(`/api/experiences/${item.id}`, body).catch(() => null);
            }
            if (item.table === "activities") {
              return api.put(`/api/experiences/activities/${item.id}`, body).catch(() => null);
            }
            return Promise.resolve(null);
          })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save corrections");
      return;
    }
    router.push("/apply");
  };

  return (
    <div className="space-y-6">
      <OnboardingBanner />
      <h1 className="text-2xl font-bold">Upload CV</h1>

      {!result && !uploading && (
        <>
          <CVDropzone onFileSelected={handleFileSelected} />
          <p className="text-center text-xs text-muted-foreground">
            Your CV text is sent to OpenAI to extract experiences — the original file is not retained after processing.
            Parsed data is stored in your account and can be deleted at any time from your{" "}
            <a href="/library" className="underline underline-offset-2 hover:text-foreground">library</a>.
          </p>
        </>
      )}

      {uploading && (
        <div className="flex flex-col items-center justify-center rounded-lg border p-12">
          <Spinner size="lg" />
          <p className="mt-4 text-sm text-muted-foreground">Extracting and parsing your CV...</p>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={() => {
              setError(null);
              setResult(null);
            }}
            className="mt-2 text-sm text-red-600 underline"
          >
            Try again
          </button>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Parsed cleanly */}
          <div className="rounded-lg border p-4">
            <p className="font-medium text-green-700">
              {result.cleanly_parsed_count} items parsed cleanly
            </p>
          </div>

          {/* Needs review */}
          {result.needs_review.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">
                Needs Your Review ({result.needs_review.length})
              </h2>
              {result.needs_review.map((item: ReviewItem) => (
                <div key={item.id} className="rounded-lg border p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">
                      {item.table} / {item.field}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Confidence: {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  {item.review_reason && (
                    <p className="text-xs text-amber-600">{item.review_reason}</p>
                  )}
                  <input
                    type="text"
                    defaultValue={item.current_value || ""}
                    onChange={(e) => handleReviewEdit(item.id, e.target.value)}
                    className="w-full rounded-md border px-3 py-2 text-sm"
                    placeholder="Enter correct value..."
                  />
                </div>
              ))}
            </div>
          )}

          {/* Unclassified blocks */}
          {result.unclassified_blocks.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">
                Couldn&apos;t Classify ({result.unclassified_blocks.length})
              </h2>
              {result.unclassified_blocks.map((block: UnclassifiedBlock) => (
                <div key={block.id} className="rounded-lg border p-4 space-y-3">
                  <p className="text-sm whitespace-pre-wrap bg-muted p-2 rounded">
                    {block.raw_text}
                  </p>
                  {block.gpt_category_guess && (
                    <p className="text-xs text-muted-foreground">
                      AI guess: {block.gpt_category_guess} (
                      {((block.gpt_confidence || 0) * 100).toFixed(0)}%)
                    </p>
                  )}
                  <div className="flex gap-2">
                    {[
                      "Work Experience",
                      "Education",
                      "Project",
                      "Activity",
                      "Skill",
                      "Ignore",
                    ].map((cat) => (
                      <button
                        key={cat}
                        onClick={() => handleResolveBlock(block.id, cat)}
                        className={`rounded-md border px-3 py-1 text-xs transition-colors ${
                          resolvedBlocks[block.id] === cat
                            ? "bg-primary text-primary-foreground"
                            : "hover:bg-muted"
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Save button */}
          <button
            onClick={handleSaveToLibrary}
            disabled={!canSave}
            className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Save & Start New Application
          </button>
        </div>
      )}
    </div>
  );
}
