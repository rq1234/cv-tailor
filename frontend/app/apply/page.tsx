"use client";

import { useState } from "react";
import { useApplication } from "@/hooks/useApplication";
import { useExperiencePool } from "@/hooks/useExperiencePool";
import { useApplyStream } from "@/hooks/useApplyStream";
import JdInputStep from "@/components/apply/JdInputStep";
import PipelineProgress from "@/components/apply/PipelineProgress";
import ExperienceSelectStep, { type PoolSelection } from "@/components/apply/ExperienceSelectStep";
import { usePipelineNotification } from "@/hooks/usePipelineNotification";
import { OnboardingBanner } from "@/components/onboarding/OnboardingBanner";

export default function ApplyPage() {
  const { createApplication, loading, error: createApplicationError } = useApplication();
  const { pool, poolLoading, fetchPool } = useExperiencePool();
  const { tailoring, pipelineSteps, pipelineError, startStream, resetStream } = useApplyStream();

  const [step, setStep] = useState(1);
  // Pre-fill from ?company= and ?role= query params (e.g. when cloning an application)
  const [companyName, setCompanyName] = useState(() => {
    if (typeof window !== "undefined") return new URLSearchParams(window.location.search).get("company") ?? "";
    return "";
  });
  const [roleTitle, setRoleTitle] = useState(() => {
    if (typeof window !== "undefined") return new URLSearchParams(window.location.search).get("role") ?? "";
    return "";
  });
  const [jdUrl, setJdUrl] = useState("");
  const [jdSource, setJdSource] = useState<"paste" | "screenshot" | "url">("paste");
  const [jdText, setJdText] = useState("");
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState<"library" | "latest_cv">("library");

  usePipelineNotification(applicationId, tailoring);

  // Step 1 → 2: create application and fetch pool for selection
  const handleJdNext = async () => {
    const app = await createApplication({
      company_name: companyName,
      role_title: roleTitle || undefined,
      jd_raw: jdText,
      jd_source: jdSource,
      jd_url: jdUrl.trim() || undefined,
    });
    if (!app) return;

    setApplicationId(app.id);
    await fetchPool();
    setStep(2);
  };

  // Step 2 → 3: start pipeline with user's selection
  const handleSelectionNext = async (selection: PoolSelection) => {
    if (!applicationId) return;
    setStep(3);
    await startStream(applicationId, selection, selectionMode);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <OnboardingBanner />
      <h1 className="text-2xl font-bold">New Application</h1>

      {/* Step indicators */}
      {(() => {
        const STEPS = ["Job Details", "Experience", "Generating"];
        return (
          <div className="flex items-center gap-0">
            {STEPS.map((label, i) => {
              const s = i + 1;
              const isActive = s === step;
              const isDone = s < step;
              return (
                <div key={s} className="flex items-center flex-1 last:flex-none">
                  <div className="flex flex-col items-center gap-1">
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                        isDone
                          ? "bg-emerald-500 text-white"
                          : isActive
                          ? "bg-blue-600 text-white shadow-sm shadow-blue-200"
                          : "bg-slate-100 text-slate-400"
                      }`}
                    >
                      {isDone ? "✓" : s}
                    </div>
                    <span
                      className={`text-[10px] font-medium whitespace-nowrap ${
                        isActive ? "text-blue-600" : isDone ? "text-emerald-600" : "text-slate-400"
                      }`}
                    >
                      {label}
                    </span>
                  </div>
                  {s < STEPS.length && (
                    <div className={`flex-1 h-0.5 mb-4 mx-1 rounded-full transition-colors ${s < step ? "bg-emerald-300" : "bg-slate-200"}`} />
                  )}
                </div>
              );
            })}
          </div>
        );
      })()}

      {/* Step 1: Job Details — company, role, and JD in one screen */}
      {step === 1 && (
        <div className="space-y-4">
          {createApplicationError && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-700">{createApplicationError}</p>
            </div>
          )}
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Company Name *</label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm"
                placeholder="e.g. Goldman Sachs"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Role Title</label>
              <input
                type="text"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm"
                placeholder="e.g. Summer Analyst"
              />
            </div>
          </div>
          <JdInputStep
            jdText={jdText}
            setJdText={setJdText}
            onNext={handleJdNext}
            nextLabel={loading ? "Creating..." : "Next"}
            nextLoading={loading}
            disabledNext={!companyName.trim()}
            onUrlFetched={(url) => {
              setJdUrl(url);
              setJdSource("url");
            }}
            onAutoFill={(company, role) => {
              if (!companyName.trim()) setCompanyName(company);
              if (!roleTitle.trim()) setRoleTitle(role);
            }}
          />
        </div>
      )}

      {/* Step 2: Select Experiences */}
      {step === 2 && (
        <div className="space-y-4">
          {/* Source mode toggle */}
          <div>
            <p className="text-sm font-medium mb-2">Source experiences from</p>
            <div className="flex gap-2">
              <button
                onClick={() => setSelectionMode("library")}
                className={`flex-1 rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
                  selectionMode === "library"
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-muted-foreground/30 bg-background text-muted-foreground hover:border-primary/50"
                }`}
              >
                Experience Library
                <span className="block text-xs font-normal opacity-75 mt-0.5">Best picks from all your history</span>
              </button>
              <button
                onClick={() => setSelectionMode("latest_cv")}
                className={`flex-1 rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
                  selectionMode === "latest_cv"
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-muted-foreground/30 bg-background text-muted-foreground hover:border-primary/50"
                }`}
              >
                Latest CV Only
                <span className="block text-xs font-normal opacity-75 mt-0.5">Only experiences from your last upload</span>
              </button>
            </div>
          </div>

          {poolLoading || !pool ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <p className="text-sm text-muted-foreground">Loading your experience pool...</p>
            </div>
          ) : (
            <ExperienceSelectStep
              pool={pool}
              onBack={() => setStep(1)}
              onNext={handleSelectionNext}
              nextLoading={tailoring}
            />
          )}
        </div>
      )}

      {/* Step 3: Pipeline Progress */}
      {step === 3 && (
        <PipelineProgress
          steps={pipelineSteps}
          error={pipelineError}
          onRetry={() => {
            setStep(2);
            resetStream();
          }}
        />
      )}
    </div>
  );
}
