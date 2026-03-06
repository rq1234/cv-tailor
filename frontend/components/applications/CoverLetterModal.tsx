"use client";

import { useEffect, useRef, useState } from "react";
import type { CoverLetterParts } from "@/hooks/useApplicationsList";
import { api } from "@/lib/api";
import { useClickOutside } from "@/hooks/useClickOutside";

interface CoverLetterModalProps {
  text: string | null;
  parts: CoverLetterParts | null;
  loading: boolean;
  onClose: () => void;
}

// Reconstruct flat text from parts (includes edits)
function buildFlatText(p: CoverLetterParts): string {
  return [
    ...p.candidate_lines,
    "",
    p.date,
    "",
    ...p.company_lines,
    "",
    p.salutation,
    "",
    ...p.paragraphs.map((para) => para + "\n"),
    p.closing,
    "",
    p.sign_off,
    p.candidate_name,
  ].join("\n");
}

export default function CoverLetterModal({ text, parts, loading, onClose }: CoverLetterModalProps) {
  const ref = useRef<HTMLDivElement>(null);

  // Editable state — reset whenever a new letter arrives
  const [editedParas, setEditedParas] = useState<string[]>([]);
  const [editedClosing, setEditedClosing] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  useEffect(() => {
    if (parts) {
      setEditedParas(parts.paragraphs);
      setEditedClosing(parts.closing);
    }
  }, [parts]);

  useClickOutside(ref, onClose);

  const currentParts: CoverLetterParts | null = parts
    ? { ...parts, paragraphs: editedParas, closing: editedClosing }
    : null;

  const handleCopy = () => {
    const src = currentParts ? buildFlatText(currentParts) : (text ?? "");
    navigator.clipboard.writeText(src);
  };

  const handleDownloadPdf = async () => {
    if (!currentParts) return;
    setPdfLoading(true);
    setPdfError(null);
    try {
      const { blob, filename } = await api.downloadFilePost("/api/export/cover-letter", {
        parts: currentParts,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : "PDF export failed.");
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        ref={ref}
        className="flex w-full max-w-3xl flex-col rounded-lg border bg-background shadow-2xl"
        style={{ maxHeight: "90vh" }}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold">Cover Letter</h2>
            {parts && (
              <p className="text-xs text-muted-foreground mt-0.5">Click any paragraph to edit</p>
            )}
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="min-h-0 flex-1 overflow-y-auto bg-muted/30 p-6">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              Generating cover letter…
            </div>
          ) : currentParts ? (
            <LetterDocument
              parts={currentParts}
              editedParas={editedParas}
              editedClosing={editedClosing}
              onParaChange={(i, v) => {
                const updated = [...editedParas];
                updated[i] = v;
                setEditedParas(updated);
              }}
              onClosingChange={setEditedClosing}
            />
          ) : text ? (
            <div className="mx-auto w-full max-w-2xl rounded bg-white px-10 py-10 shadow-md">
              <pre
                className="whitespace-pre-wrap text-sm leading-7 text-gray-900"
                style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
              >
                {text}
              </pre>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        {(text || parts) && !loading && (
          <div className="flex shrink-0 items-center justify-between border-t px-5 py-3">
            <div>
              {pdfError && <p className="text-xs text-red-600">{pdfError}</p>}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleDownloadPdf}
                disabled={!currentParts || pdfLoading}
                className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
              >
                {pdfLoading ? "Generating…" : "Download PDF"}
              </button>
              <button
                onClick={handleCopy}
                className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted"
              >
                Copy to clipboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** Renders the cover letter with proper UK formal letter layout. */
function LetterDocument({
  parts,
  editedParas,
  editedClosing,
  onParaChange,
  onClosingChange,
}: {
  parts: CoverLetterParts;
  editedParas: string[];
  editedClosing: string;
  onParaChange: (index: number, value: string) => void;
  onClosingChange: (value: string) => void;
}) {
  return (
    <div
      className="mx-auto w-full max-w-2xl rounded bg-white px-12 py-10 shadow-md text-gray-900"
      style={{
        fontFamily: "Georgia, 'Times New Roman', serif",
        fontSize: "12.5px",
        lineHeight: "1.7",
        color: "#1a1a1a",
      }}
    >
      {/* ── Candidate block — right-aligned, read-only ── */}
      <div className="flex justify-end mb-10">
        <div style={{ textAlign: "right" }}>
          {parts.candidate_lines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      </div>

      {/* ── Date — read-only ── */}
      <div className="mb-5">{parts.date}</div>

      {/* ── Company address — read-only ── */}
      <div className="mb-7">
        {parts.company_lines.map((line, i) => (
          <div key={i}>{line}</div>
        ))}
      </div>

      {/* ── Salutation — read-only ── */}
      <div className="mb-5">{parts.salutation}</div>

      {/* ── Body paragraphs — editable ── */}
      {editedParas.map((para, i) => (
        <EditableArea
          key={i}
          value={para}
          onChange={(v) => onParaChange(i, v)}
          className="mb-4"
        />
      ))}

      {/* ── Closing sentence — editable ── */}
      <EditableArea value={editedClosing} onChange={onClosingChange} className="mb-7" />

      {/* ── Sign-off — read-only ── */}
      <div>
        <div>{parts.sign_off}</div>
        <div className="mt-1">{parts.candidate_name}</div>
      </div>
    </div>
  );
}

/** Auto-resizing textarea that looks like a letter paragraph. */
function EditableArea({
  value,
  onChange,
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  const taRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize on mount and value change
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }, [value]);

  return (
    <textarea
      ref={taRef}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={1}
      className={`w-full resize-none border-0 bg-transparent p-0 focus:outline-none focus:bg-amber-50 rounded transition-colors ${className}`}
      style={{
        fontFamily: "inherit",
        fontSize: "inherit",
        lineHeight: "inherit",
        color: "inherit",
        textAlign: "justify",
        overflow: "hidden",
      }}
    />
  );
}
