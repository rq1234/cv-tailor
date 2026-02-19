"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { experiencePoolSchema, type ExperiencePool } from "@/lib/schemas";
import { useAppStore } from "@/store/appStore";

export function useExperiencePool() {
  const { pool, poolLoading, setPool, setPoolLoading } = useAppStore();
  const [poolError, setPoolError] = useState<string | null>(null);

  const fetchPool = useCallback(async () => {
    setPoolLoading(true);
    setPoolError(null);
    try {
      const data = await api.get<ExperiencePool>("/api/cv/pool");
      const validated = experiencePoolSchema.parse(data);
      setPool(validated);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to load";
      console.error("Failed to fetch experience pool:", msg);
      setPoolError(msg);
      setPool({ work_experiences: [], education: [], projects: [], activities: [], skills: [], profile: null });
    } finally {
      setPoolLoading(false);
    }
  }, [setPool, setPoolLoading]);

  return { pool, poolLoading, poolError, fetchPool };
}
