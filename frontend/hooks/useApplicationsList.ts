"use client";

import { useCallback, useState } from "react";
import { z } from "zod";
import { api } from "@/lib/api";
import { applicationSchema, type Application, type OutcomeValue } from "@/lib/schemas";

export interface CoverLetterParts {
  candidate_lines: string[];
  date: string;
  company_lines: string[];
  salutation: string;
  paragraphs: string[];
  closing: string;
  sign_off: string;
  candidate_name: string;
}

export interface AppStats {
  total: number;
  by_outcome: Record<string, number>;
  avg_ats_score: number | null;
  by_domain: {
    domain: string;
    count: number;
    avg_ats_score: number | null;
    offer_rate: number;
    interview_rate: number;
  }[];
}

export interface GapRec {
  domain: string;
  gap: string;
  count: number;
  companies: string[];
}

export function useApplicationsList() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [stats, setStats] = useState<AppStats | null>(null);
  const [gapRecs, setGapRecs] = useState<GapRec[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Per-item loading: tracked by ID string
  const [savingOutcomeId, setSavingOutcomeId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [retailoringId, setRetailoringId] = useState<string | null>(null);

  // Cover letter (one at a time)
  const [coverLetterId, setCoverLetterId] = useState<string | null>(null);
  const [coverLetterText, setCoverLetterText] = useState<string | null>(null);
  const [coverLetterParts, setCoverLetterParts] = useState<CoverLetterParts | null>(null);
  const [coverLetterLoading, setCoverLetterLoading] = useState(false);

  const fetchApplications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, statsData, gapData] = await Promise.all([
        api.get<Application[]>("/api/applications"),
        api.get<AppStats>("/api/applications/stats/summary").catch((e) => { console.error("Stats fetch failed:", e); return null; }),
        api.get<{ recommendations: GapRec[] }>("/api/applications/gap-recommendations").catch((e) => { console.error("Gap recs fetch failed:", e); return null; }),
      ]);
      setApplications(z.array(applicationSchema).parse(data));
      if (statsData) setStats(statsData);
      if (gapData) setGapRecs(gapData.recommendations);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load applications");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleOutcomeChange = useCallback(async (appId: string, outcome: OutcomeValue | "") => {
    setSavingOutcomeId(appId);
    try {
      await api.patch(`/api/applications/${appId}`, { outcome: outcome || null });
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, outcome: outcome || null } : a))
      );
    } finally {
      setSavingOutcomeId(null);
    }
  }, []);

  const handleRetailor = useCallback(async (appId: string) => {
    setRetailoringId(appId);
    try {
      await api.post(`/api/tailor/re-tailor/${appId}`);
      await fetchApplications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start re-tailoring");
    } finally {
      setRetailoringId(null);
    }
  }, [fetchApplications]);

  const handleDelete = useCallback(async (appId: string) => {
    setDeletingId(appId);
    try {
      await api.delete(`/api/applications/${appId}`);
      setApplications((prev) => prev.filter((a) => a.id !== appId));
    } finally {
      setDeletingId(null);
    }
  }, []);

  const handleSaveNotes = useCallback(async (appId: string, notes: string) => {
    await api.patch(`/api/applications/${appId}`, { notes: notes || null });
    setApplications((prev) =>
      prev.map((a) => (a.id === appId ? { ...a, notes: notes || null } : a))
    );
  }, []);

  const handleGenerateCoverLetter = useCallback(async (appId: string) => {
    setCoverLetterId(appId);
    setCoverLetterText(null);
    setCoverLetterParts(null);
    setCoverLetterLoading(true);
    try {
      const data = await api.post<{ cover_letter: string; parts: CoverLetterParts | null }>(
        `/api/applications/${appId}/cover-letter`
      );
      setCoverLetterText(data.cover_letter);
      setCoverLetterParts(data.parts ?? null);
    } catch (err) {
      setCoverLetterText(err instanceof Error ? `Error: ${err.message}` : "Failed to generate cover letter.");
    } finally {
      setCoverLetterLoading(false);
    }
  }, []);

  const clearCoverLetter = useCallback(() => {
    setCoverLetterId(null);
    setCoverLetterText(null);
    setCoverLetterParts(null);
  }, []);

  return {
    applications,
    stats,
    gapRecs,
    loading,
    error,
    savingOutcomeId,
    deletingId,
    retailoringId,
    coverLetterId,
    coverLetterText,
    coverLetterParts,
    coverLetterLoading,
    fetchApplications,
    handleOutcomeChange,
    handleRetailor,
    handleDelete,
    handleSaveNotes,
    handleGenerateCoverLetter,
    clearCoverLetter,
  };
}
