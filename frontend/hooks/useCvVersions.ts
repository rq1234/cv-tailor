"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useAsyncState } from "./useAsyncState";

export interface CvVersionEntry {
  id: string;
  created_at: string;
  ats_score: number | null;
  baseline_ats_score: number | null;
}

export function useCvVersions(applicationId: string) {
  const [versions, setVersions] = useState<CvVersionEntry[]>([]);
  const { loading, run } = useAsyncState();

  const fetchVersions = useCallback(async () => {
    await run(async () => {
      const data = await api.get<CvVersionEntry[]>(`/api/tailor/versions/${applicationId}`);
      setVersions(data);
    });
  }, [applicationId, run]);

  return { versions, loading, fetchVersions };
}
