import { create } from "zustand";
import type { ExperiencePool, ParseSummary } from "@/lib/schemas";

interface PipelineStep {
  step: string;
  status: "running" | "done" | "error";
  label: string;
  progress: number;
  total: number;
}

interface AppState {
  // Experience pool
  pool: ExperiencePool | null;
  poolLoading: boolean;
  setPool: (pool: ExperiencePool) => void;
  setPoolLoading: (loading: boolean) => void;

  // Upload state
  uploadResult: ParseSummary | null;
  uploadLoading: boolean;
  setUploadResult: (result: ParseSummary | null) => void;
  setUploadLoading: (loading: boolean) => void;

  // Active application
  activeApplicationId: string | null;
  setActiveApplicationId: (id: string | null) => void;

  // Tailoring pipeline progress
  pipeline: PipelineStep | null;
  pipelineError: string | null;
  setPipeline: (step: PipelineStep | null) => void;
  setPipelineError: (error: string | null) => void;
  clearPipeline: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  pool: null,
  poolLoading: false,
  setPool: (pool) => set({ pool }),
  setPoolLoading: (poolLoading) => set({ poolLoading }),

  uploadResult: null,
  uploadLoading: false,
  setUploadResult: (uploadResult) => set({ uploadResult }),
  setUploadLoading: (uploadLoading) => set({ uploadLoading }),

  activeApplicationId: null,
  setActiveApplicationId: (activeApplicationId) => set({ activeApplicationId }),

  pipeline: null,
  pipelineError: null,
  setPipeline: (pipeline) => set({ pipeline }),
  setPipelineError: (pipelineError) => set({ pipelineError }),
  clearPipeline: () => set({ pipeline: null, pipelineError: null }),
}));
