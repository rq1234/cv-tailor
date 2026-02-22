import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { JD_MAX_CHARS } from "@/lib/schemas";

type JdSource = "paste" | "screenshot";

interface JdInputStepProps {
  jdText: string;
  setJdText: (text: string) => void;
  onBack: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextLoading?: boolean;
}

export default function JdInputStep({ jdText, setJdText, onBack, onNext, nextLabel = "Next", nextLoading = false }: JdInputStepProps) {
  const [jdSource, setJdSource] = useState<JdSource>("paste");
  const [screenshotPreview, setScreenshotPreview] = useState<string | null>(null);
  const [screenshotExtracting, setScreenshotExtracting] = useState(false);
  const [screenshotError, setScreenshotError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const objectUrlRef = useRef<string | null>(null);

  // Revoke object URL on unmount to free memory
  useEffect(() => {
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, []);

  const handleScreenshotFile = useCallback(async (file: File) => {
    const allowedTypes = ["image/png", "image/jpeg", "image/webp", "image/gif"];
    if (!allowedTypes.includes(file.type)) {
      setScreenshotError("Please upload a PNG, JPEG, WebP, or GIF image.");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setScreenshotError("Image too large. Maximum size is 20 MB.");
      return;
    }

    setScreenshotError(null);
    // Revoke any previous object URL before creating a new one
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const objectUrl = URL.createObjectURL(file);
    objectUrlRef.current = objectUrl;
    setScreenshotPreview(objectUrl);
    setScreenshotExtracting(true);
    try {
      const result = await api.uploadScreenshot(file);
      setJdText(result.extracted_text);
    } catch (err) {
      setScreenshotError(err instanceof Error ? err.message : "Failed to extract text from screenshot");
    } finally {
      setScreenshotExtracting(false);
    }
  }, [setJdText]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const file = e.dataTransfer.files[0];
      if (file) handleScreenshotFile(file);
    },
    [handleScreenshotFile]
  );

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Job Description</h2>

      <div className="flex gap-1 rounded-lg border p-1">
        {(["paste", "screenshot"] as const).map((source) => (
          <button
            key={source}
            onClick={() => setJdSource(source)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              jdSource === source
                ? "bg-primary text-primary-foreground"
                : "hover:bg-muted"
            }`}
          >
            {source === "paste" ? "Paste" : "Screenshot"}
          </button>
        ))}
      </div>

      {jdSource === "paste" && (
        <div className="space-y-1">
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            className={`w-full rounded-md border px-3 py-2 text-sm min-h-[300px] ${
              jdText.length > JD_MAX_CHARS ? "border-red-400" : ""
            }`}
            placeholder="Paste the full job description here..."
          />
          <div className="flex justify-end">
            <span
              className={`text-xs ${
                jdText.length > JD_MAX_CHARS
                  ? "text-red-600 font-medium"
                  : "text-muted-foreground"
              }`}
            >
              {jdText.length.toLocaleString()} / {JD_MAX_CHARS.toLocaleString()}
            </span>
          </div>
          {jdText.length > JD_MAX_CHARS && (
            <p className="text-xs text-red-600">
              Job description is too long. Please shorten it to under {JD_MAX_CHARS.toLocaleString()} characters.
            </p>
          )}
        </div>
      )}

      {jdSource === "screenshot" && (
        <div className="space-y-4">
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
            onClick={() => fileInputRef.current?.click()}
            className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
              dragActive
                ? "border-primary bg-primary/5"
                : screenshotPreview
                ? "border-green-300 bg-green-50"
                : "border-muted-foreground/25 hover:border-primary/50"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleScreenshotFile(file);
              }}
            />

            {screenshotExtracting ? (
              <div className="space-y-2">
                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                <p className="text-sm font-medium">Extracting text from screenshot...</p>
                <p className="text-xs text-muted-foreground">This may take a few seconds</p>
              </div>
            ) : screenshotPreview ? (
              <div className="space-y-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={screenshotPreview} alt="Screenshot preview" className="mx-auto max-h-48 rounded-md object-contain" />
                <p className="text-sm text-green-700 font-medium">Text extracted successfully</p>
                <p className="text-xs text-muted-foreground">Click or drop a new image to replace</p>
              </div>
            ) : (
              <div className="space-y-2">
                <svg className="mx-auto h-10 w-10 text-muted-foreground/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="text-sm font-medium">Drop a screenshot here, or click to browse</p>
                <p className="text-xs text-muted-foreground">PNG, JPEG, WebP, or GIF up to 20 MB</p>
              </div>
            )}
          </div>

          {screenshotError && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-700">{screenshotError}</p>
            </div>
          )}

          {jdText && (
            <div className="space-y-2">
              <label className="block text-sm font-medium">Extracted Text (editable)</label>
              <textarea
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm min-h-[200px]"
              />
            </div>
          )}
        </div>
      )}

      <div className="flex gap-3">
        <button onClick={onBack} className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted">
          Back
        </button>
        <button
          onClick={onNext}
          disabled={!jdText.trim() || jdText.length > JD_MAX_CHARS || nextLoading}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {nextLoading ? "Starting..." : nextLabel}
        </button>
      </div>
    </div>
  );
}
