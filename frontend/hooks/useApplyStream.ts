"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAppStore } from "@/store/appStore";
import type { PoolSelection } from "@/components/apply/ExperienceSelectStep";
import type { PipelineStatus } from "@/lib/schemas";

export interface PipelineStep {
  step: string;
  status: "running" | "done" | "error";
  label: string;
  progress: number;
  total: number;
}

const MAX_RETRIES = 3;

/**
 * Owns the SSE streaming lifecycle: connection, buffer parsing, retry/backoff,
 * 409 conflict recovery, and navigation on completion.
 */
export function useApplyStream() {
  const router = useRouter();
  const { setPipeline, setPipelineError, clearPipeline } = useAppStore();

  const [tailoring, setTailoring] = useState(false);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [pipelineError, setPipelineErrorLocal] = useState<string | null>(null);
  const [completedApplicationId, setCompletedApplicationId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      clearPipeline();
    };
  }, [clearPipeline]);

  const runStream = useCallback(async (
    appId: string,
    selection: PoolSelection,
    retriesLeft: number = MAX_RETRIES,
    mode: "library" | "latest_cv" = "library",
  ): Promise<void> => {
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
        selection_mode: mode,
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
                setCompletedApplicationId(appId);
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

      if (retriesLeft > 0) {
        const attempt = MAX_RETRIES - retriesLeft + 1;
        const waitMs = 1_000 * 2 ** (attempt - 1);
        setPipelineErrorLocal(`Connection lost — retrying in ${waitMs / 1000}s…`);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
        if (!controller.signal.aborted) {
          setPipelineErrorLocal(null);
          return runStream(appId, selection, retriesLeft - 1, mode);
        }
      } else {
        await handleStreamError(err, appId);
      }
    }
  }, [router, setPipeline, setPipelineError, clearPipeline]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStreamError = async (err: unknown, appId: string) => {
    const is409 = err instanceof ApiError && err.status === 409;
    try {
      const status = await api.get<PipelineStatus>(`/api/tailor/status/${appId}`);
      if (status.cv_version_id) {
        clearPipeline();
        setTailoring(false);
        setCompletedApplicationId(appId);
        return;
      }
      if (is409 && status.pipeline_started_at) {
        setPipelineErrorLocal("A tailoring job is already running. Please wait for it to finish, then visit your Applications page to view results.");
      } else {
        const errMsg = status.pipeline_error || (err instanceof Error ? err.message : "Tailoring failed");
        setPipelineErrorLocal(errMsg);
        setPipelineError(errMsg);
      }
    } catch {
      const errMsg = err instanceof Error ? err.message : "Tailoring failed";
      setPipelineErrorLocal(errMsg);
      setPipelineError(errMsg);
    }
    setTailoring(false);
  };

  const startStream = useCallback(async (
    appId: string,
    selection: PoolSelection,
    mode: "library" | "latest_cv" = "library",
  ) => {
    setTailoring(true);
    setPipelineSteps([]);
    setPipelineErrorLocal(null);
    setCompletedApplicationId(null);
    clearPipeline();
    await runStream(appId, selection, MAX_RETRIES, mode);
  }, [runStream, clearPipeline]);

  const resetStream = useCallback(() => {
    setPipelineErrorLocal(null);
    setCompletedApplicationId(null);
    clearPipeline();
  }, [clearPipeline]);

  return { tailoring, pipelineSteps, pipelineError, completedApplicationId, startStream, resetStream };
}
