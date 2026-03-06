"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

const STORAGE_KEY = "cv-onboarded";

const STEPS = [
  { num: 1, label: "Upload CV", icon: "📄" },
  { num: 2, label: "Paste job ad", icon: "📋" },
  { num: 3, label: "Review bullets", icon: "✏️" },
  { num: 4, label: "Download PDF", icon: "⬇️" },
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
    <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 mb-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <p className="text-sm font-semibold text-blue-800 mb-2">How CV Tailor works</p>
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            {STEPS.map((step, i) => (
              <div key={step.num} className="flex items-center gap-1.5 text-sm text-blue-700">
                <span className="text-base">{step.icon}</span>
                <span>
                  <span className="font-medium">{step.num}.</span> {step.label}
                </span>
                {i < STEPS.length - 1 && (
                  <span className="text-blue-300 hidden sm:inline">→</span>
                )}
              </div>
            ))}
          </div>
        </div>
        <button
          onClick={dismiss}
          className="flex-shrink-0 text-blue-400 hover:text-blue-600 transition-colors"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
