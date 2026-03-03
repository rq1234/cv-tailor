"use client";

import { useState } from "react";
import type { BulletDecision, ExperienceDiff } from "./types";
import { bulletText } from "./types";

interface PlaceholderBannerProps {
  diffJson: Record<string, ExperienceDiff>;
  onApply: (expId: string, idx: number, decision: BulletDecision, newText: string) => void;
}

export default function PlaceholderBanner({ diffJson, onApply }: PlaceholderBannerProps) {
  const [showModal, setShowModal] = useState(false);
  const [placeholderValues, setPlaceholderValues] = useState<Record<string, string>>({});

  const placeholderBullets = Object.entries(diffJson || {}).flatMap(([expId, diff]) =>
    diff.suggested_bullets
      .map((b, idx) => ({ expId, idx, text: bulletText(b) }))
      .filter((item) => item.text.includes("[X]"))
  );

  if (placeholderBullets.length === 0) return null;

  const handleApply = () => {
    for (const { expId, idx, text } of placeholderBullets) {
      const key = `${expId}_${idx}`;
      const val = placeholderValues[key];
      if (val?.trim()) {
        onApply(expId, idx, "edit", text.replace(/\[X\]/g, val.trim()));
      }
    }
    setShowModal(false);
  };

  return (
    <>
      <div className="flex items-center justify-between rounded-md border border-orange-200 bg-orange-50 px-4 py-2.5 text-sm text-orange-800">
        <span>
          <span className="font-semibold">{placeholderBullets.length}</span> bullet
          {placeholderBullets.length !== 1 ? "s have" : " has"} unfilled{" "}
          <code className="rounded bg-orange-100 px-1 text-xs">[X]</code> placeholders.
        </span>
        <button
          onClick={() => setShowModal(true)}
          className="rounded-md bg-orange-600 px-3 py-1 text-xs font-medium text-white hover:bg-orange-700"
        >
          Fill now
        </button>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg border bg-background shadow-xl">
            <div className="flex items-center justify-between border-b px-5 py-3">
              <h2 className="text-sm font-semibold">Fill Placeholders</h2>
              <button onClick={() => setShowModal(false)} className="text-muted-foreground hover:text-foreground">✕</button>
            </div>
            <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
              <p className="text-xs text-muted-foreground">
                Enter the value to replace each <code className="rounded bg-muted px-0.5">[X]</code> placeholder. Leave blank to keep as-is.
              </p>
              {placeholderBullets.map(({ expId, idx, text }) => {
                const key = `${expId}_${idx}`;
                return (
                  <div key={key} className="space-y-1.5">
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {text.split("[X]").map((part, i, arr) => (
                        <span key={i}>
                          {part}
                          {i < arr.length - 1 && (
                            <span className="rounded bg-orange-100 px-0.5 font-mono text-orange-700">[X]</span>
                          )}
                        </span>
                      ))}
                    </p>
                    <input
                      type="text"
                      value={placeholderValues[key] ?? ""}
                      onChange={(e) => setPlaceholderValues((prev) => ({ ...prev, [key]: e.target.value }))}
                      placeholder="e.g. 40%, £2M, 3 months…"
                      className="w-full rounded border px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>
                );
              })}
            </div>
            <div className="border-t px-5 py-3 flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
                Cancel
              </button>
              <button onClick={handleApply} className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
