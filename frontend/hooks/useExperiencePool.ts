"use client";

import { useCallback } from "react";
import { api } from "@/lib/api";
import { experiencePoolSchema, type ExperiencePool } from "@/lib/schemas";
import { useAppStore } from "@/store/appStore";

export function useExperiencePool() {
  const { pool, poolLoading, setPool, setPoolLoading } = useAppStore();

  const fetchPool = useCallback(async () => {
    setPoolLoading(true);
    try {
      const data = await api.get<ExperiencePool>("/api/cv/pool");
      const validated = experiencePoolSchema.parse(data);
      setPool(validated);
    } catch (error) {
      console.error("Failed to fetch experience pool:", error);
    } finally {
      setPoolLoading(false);
    }
  }, [setPool, setPoolLoading]);

  return { pool, poolLoading, fetchPool };
}
