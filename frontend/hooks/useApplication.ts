"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { applicationSchema, type Application } from "@/lib/schemas";

export function useApplication() {
  const [application, setApplication] = useState<Application | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createApplication = useCallback(
    async (data: {
      company_name: string;
      role_title?: string;
      jd_raw: string;
      jd_source?: string;
    }) => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.post<Application>("/api/applications", data);
        const validated = applicationSchema.parse(result);
        setApplication(validated);
        return validated;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to create application";
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const fetchApplication = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<Application>(`/api/applications/${id}`);
      const validated = applicationSchema.parse(result);
      setApplication(validated);
      return validated;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to fetch application";
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { application, loading, error, createApplication, fetchApplication };
}
