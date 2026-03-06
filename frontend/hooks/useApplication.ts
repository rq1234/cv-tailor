"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { applicationSchema, type Application } from "@/lib/schemas";
import { useAsyncState } from "./useAsyncState";

export function useApplication() {
  const [application, setApplication] = useState<Application | null>(null);
  const { loading, error, run } = useAsyncState();

  const createApplication = useCallback(
    async (data: {
      company_name: string;
      role_title?: string;
      jd_raw: string;
      jd_source?: string;
      jd_url?: string;
    }) => {
      return run(async () => {
        const result = await api.post<Application>("/api/applications", data);
        const validated = applicationSchema.parse(result);
        setApplication(validated);
        return validated;
      }, "Failed to create application");
    },
    [run]
  );

  const fetchApplication = useCallback(async (id: string) => {
    return run(async () => {
      const result = await api.get<Application>(`/api/applications/${id}`);
      const validated = applicationSchema.parse(result);
      setApplication(validated);
      return validated;
    }, "Failed to fetch application");
  }, [run]);

  return { application, loading, error, createApplication, fetchApplication };
}
