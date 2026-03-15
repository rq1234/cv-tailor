"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

const STORAGE_KEY = "cv-onboarded";

const STEPS = [
  { num: 1, label: "Upload your CV", detail: "Import your existing resume" },
  { num: 2, label: "Paste a job ad", detail: "Add the role you're applying to" },
  { num: 3, label: "Review suggestions", detail: "Accept, edit, or reject bullets" },
  { num: 4, label: "Export & apply", detail: "Download a tailored PDF" },
];

export function OnboardingBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
    } catch {
      // localStorage not available (SSR or private mode)
    }
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch { /* ignore */ }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="rounded-xl border border-border bg-card shadow-sm px-5 py-4 mb-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-black uppercase tracking-widest text-muted-foreground mb-3">How it works</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {STEPS.map((step) => (
              <div key={step.num} className="flex items-start gap-2.5">
                <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-black text-white">
                  {step.num}
                </span>
                <div>
                  <p className="text-sm font-semibold text-foreground leading-tight">{step.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{step.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <button
          onClick={dismiss}
          className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
