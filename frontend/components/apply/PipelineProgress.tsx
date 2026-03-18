"use client";

import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";

interface PipelineStep {
  step: string;
  status: "running" | "done" | "error";
  label: string;
  progress: number;
  total: number;
}

const PIPELINE_STAGES = [
  { key: "parsing_jd",            label: "Parsing job description" },
  { key: "selecting_experiences", label: "Selecting best experiences" },
  { key: "baseline_ats_check",    label: "Checking baseline ATS score" },
  { key: "analyzing_gaps",        label: "Mapping experience to requirements" },
  { key: "tailoring_cv",          label: "Tailoring bullet points" },
  { key: "tailoring_projects",    label: "Tailoring projects & activities" },
  { key: "checking_ats",          label: "Checking ATS compliance" },
  { key: "saving",                label: "Saving results" },
];

interface PipelineProgressProps {
  steps: PipelineStep[];
  error: string | null;
  onRetry: () => void;
}

export default function PipelineProgress({ steps, error, onRetry }: PipelineProgressProps) {
  const [elapsed, setElapsed] = useState(0);
  const isActive = steps.length > 0 && !error;
  const isDone = PIPELINE_STAGES.every((s) => {
    const events = steps.filter((e) => e.step === s.key);
    return events.length > 0 && events[events.length - 1].status === "done";
  });

  useEffect(() => {
    if (!isActive || isDone) return;
    const interval = setInterval(() => setElapsed((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [isActive, isDone]);

  const completedCount = PIPELINE_STAGES.filter((s) => {
    const events = steps.filter((e) => e.step === s.key);
    return events.length > 0 && events[events.length - 1].status === "done";
  }).length;

  const overallPct = Math.round((completedCount / PIPELINE_STAGES.length) * 100);

  const elapsedLabel =
    elapsed > 0
      ? elapsed >= 60
        ? `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`
        : `${elapsed}s`
      : null;

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <h2 className="text-lg font-semibold">Tailoring in Progress</h2>
          {elapsedLabel && !isDone && (
            <span className="text-xs text-slate-400">{elapsedLabel}</span>
          )}
        </div>
        {/* Overall progress bar */}
        <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
          <div
            className={`h-1.5 rounded-full transition-all duration-700 ${isDone ? "bg-emerald-500" : "bg-blue-500"}`}
            style={{ width: `${overallPct}%` }}
          />
        </div>
      </div>

      {/* Stepper */}
      <div className="relative">
        {PIPELINE_STAGES.map((pipeStep, stageIdx) => {
          const stepEvents = steps.filter((s) => s.step === pipeStep.key);
          const latest = stepEvents[stepEvents.length - 1] ?? null;
          const latestStatus = latest?.status ?? null;
          const completed = latestStatus === "done";
          const running = latestStatus === "running";
          const errored = latestStatus === "error";
          const isLast = stageIdx === PIPELINE_STAGES.length - 1;

          // Sub-progress for tailoring step
          const showSubProgress =
            pipeStep.key === "tailoring_cv" &&
            running &&
            latest?.total > 0;

          return (
            <div key={pipeStep.key} className="flex gap-4">
              {/* Connector column */}
              <div className="flex flex-col items-center">
                {/* Step circle */}
                <div
                  className={`relative z-10 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border-2 transition-all duration-300 ${
                    completed
                      ? "border-emerald-500 bg-emerald-500 text-white"
                      : errored
                      ? "border-red-500 bg-red-500 text-white"
                      : running
                      ? "border-blue-500 bg-white"
                      : "border-slate-200 bg-white"
                  }`}
                >
                  {completed ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : errored ? (
                    <X className="h-3.5 w-3.5" />
                  ) : running ? (
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                  ) : (
                    <div className="h-2 w-2 rounded-full bg-slate-200" />
                  )}
                </div>

                {/* Connector line */}
                {!isLast && (
                  <div className="w-0.5 flex-1 min-h-[1.5rem]">
                    <div
                      className={`w-full h-full transition-colors duration-500 ${
                        completed ? "bg-emerald-300" : "bg-slate-100"
                      }`}
                    />
                  </div>
                )}
              </div>

              {/* Step content */}
              <div className={`pb-5 ${isLast ? "pb-0" : ""} flex-1 min-w-0`}>
                <span
                  className={`text-sm transition-colors duration-200 ${
                    completed
                      ? "text-emerald-700 font-medium"
                      : errored
                      ? "text-red-700 font-medium"
                      : running
                      ? "animate-pulse text-blue-700 font-medium"
                      : "text-slate-400"
                  }`}
                >
                  {pipeStep.label}
                </span>

                {/* Sub-progress for tailoring */}
                {showSubProgress && (
                  <div className="mt-1.5">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs text-slate-400">
                        {latest.progress} / {latest.total} bullets
                      </span>
                    </div>
                    <div className="h-1 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-1 rounded-full bg-blue-400 transition-all duration-500"
                        style={{ width: `${Math.round((latest.progress / latest.total) * 100)}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={onRetry} className="mt-2 text-sm text-red-600 underline">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
