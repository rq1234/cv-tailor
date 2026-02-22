"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useApplication } from "@/hooks/useApplication";
import { api, ApiError } from "@/lib/api";
import { useAppStore } from "@/store/appStore";
import { useExperiencePool } from "@/hooks/useExperiencePool";
import JdInputStep from "@/components/apply/JdInputStep";
import PipelineProgress from "@/components/apply/PipelineProgress";
import ExperienceSelectStep, { type PoolSelection } from "@/components/apply/ExperienceSelectStep";

interface PipelineStep {
  step: string;
  status: "running" | "done" | "error";
  label: string;
  progress: number;
  total: number;
}

const MAX_RETRIES = 3;

export default function ApplyPage() {
  const router = useRouter();
  const { createApplication, loading } = useApplication();
  const { setPipeline, setPipelineError, clearPipeline } = useAppStore();
  const { pool, poolLoading, fetchPool } = useExperiencePool();

  const [step, setStep] = useState(1);
  const [companyName, setCompanyName] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [jdText, setJdText] = useState("");
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [pipelineError, setPipelineErrorLocal] = useState<string | null>(null);

  // Abort controller ref — cancelled on unmount to stop any in-flight stream
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      clearPipeline();
    };
  }, [clearPipeline]);

  const runStream = async (
    appId: string,
    selection: PoolSelection,
    retriesLeft: number,
  ): Promise<void> => {
    // Abort any previous stream before starting a new one.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await api.stream("/api/tailor/run", {
        application_id: appId,
        pinned_experiences: selection.experience_ids,
        pinned_projects: selection.project_ids,
        pinned_activities: selection.activity_ids,
        pinned_education: selection.education_ids,
        pinned_skills: selection.skill_ids,
      });

      if (controller.signal.aborted) return;

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error("No response stream");

      let buffer = "";
      while (true) {
        if (controller.signal.aborted) {
          reader.cancel();
          return;
        }

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.step) {
                const stepData: PipelineStep = data;
                setPipelineSteps((prev) => [...prev, stepData]);
                setPipeline(stepData);
              }
              if (data.error) {
                const errMsg = data.error as string;
                setPipelineErrorLocal(errMsg);
                setPipelineError(errMsg);
                setTailoring(false);
                return;
              }
              if (data.cv_version_id) {
                clearPipeline();
                setTailoring(false);
                router.push(`/review/${appId}`);
                return;
              }
            } catch {
              // Skip malformed SSE lines
            }
          }
        }
      }
    } catch (err) {
      if (controller.signal.aborted) return;

      // Retry on network errors with exponential backoff
      if (retriesLeft > 0) {
        const attempt = MAX_RETRIES - retriesLeft + 1;
        const waitMs = 1_000 * 2 ** (attempt - 1);
        setPipelineErrorLocal(`Connection lost — retrying in ${waitMs / 1000}s…`);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
        if (!controller.signal.aborted) {
          setPipelineErrorLocal(null);
          return runStream(appId, selection, retriesLeft - 1);
        }
      } else {
        // 409 means the backend already has a pipeline running for this user.
        const is409 = err instanceof ApiError && err.status === 409;
        const errMsg = is409
          ? "A tailoring job is already running. Please wait for it to finish."
          : err instanceof Error ? err.message : "Tailoring failed";
        setPipelineErrorLocal(errMsg);
        setPipelineError(errMsg);
        setTailoring(false);
      }
    }
  };

  // Step 2 → 3: create application and fetch pool for selection
  const handleJdNext = async () => {
    const app = await createApplication({
      company_name: companyName,
      role_title: roleTitle || undefined,
      jd_raw: jdText,
      jd_source: "paste",
    });
    if (!app) return;

    setApplicationId(app.id);
    await fetchPool();
    setStep(3);
  };

  // Step 3 → 4: start pipeline with user's selection
  const handleSelectionNext = async (selection: PoolSelection) => {
    if (!applicationId) return;

    setTailoring(true);
    setStep(4);
    setPipelineSteps([]);
    setPipelineErrorLocal(null);
    clearPipeline();

    await runStream(applicationId, selection, MAX_RETRIES);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">New Application</h1>

      {/* Step indicators */}
      <div className="flex gap-2">
        {[1, 2, 3, 4].map((s) => (
          <div
            key={s}
            className={`h-2 flex-1 rounded-full ${s <= step ? "bg-primary" : "bg-muted"}`}
          />
        ))}
      </div>

      {/* Step 1: Company & Role */}
      {step === 1 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Company & Role</h2>
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
          <button
            onClick={() => setStep(2)}
            disabled={!companyName.trim()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      {/* Step 2: JD Input */}
      {step === 2 && (
        <JdInputStep
          jdText={jdText}
          setJdText={setJdText}
          onBack={() => setStep(1)}
          onNext={handleJdNext}
          nextLabel={loading ? "Creating..." : "Next"}
          nextLoading={loading}
        />
      )}

      {/* Step 3: Select Experiences */}
      {step === 3 && (
        poolLoading || !pool ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <p className="text-sm text-muted-foreground">Loading your experience pool...</p>
          </div>
        ) : (
          <ExperienceSelectStep
            pool={pool}
            onBack={() => setStep(2)}
            onNext={handleSelectionNext}
            nextLoading={tailoring}
          />
        )
      )}

      {/* Step 4: Pipeline Progress */}
      {step === 4 && (
        <PipelineProgress
          steps={pipelineSteps}
          error={pipelineError}
          onRetry={() => {
            setStep(3);
            setPipelineErrorLocal(null);
            clearPipeline();
          }}
        />
      )}
    </div>
  );
}
