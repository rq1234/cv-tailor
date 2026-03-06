"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { type BulletState, type TailorResult, bulletText } from "@/components/review/types";

interface AcceptChangesPayload {
  acceptedChanges: Record<string, string[] | unknown>;
  rejectedChanges: Record<string, number[]>;
}

function buildChanges(
  result: TailorResult,
  decisions: Record<string, Record<number, BulletState>>,
  manualEdits: Record<string, string>
): AcceptChangesPayload {
  const acceptedChanges: Record<string, string[] | unknown> = {};
  const rejectedChanges: Record<string, number[]> = {};

  for (const [expId, expDecisions] of Object.entries(decisions)) {
    const diff = result.diff_json[expId];
    if (!diff) continue;

    const acceptedBullets: string[] = [];
    const rejectedIndices: number[] = [];

    for (const [idxStr, bullet] of Object.entries(expDecisions)) {
      const idx = parseInt(idxStr);
      // Guard against stale indices from localStorage after re-tailoring
      if (idx >= diff.suggested_bullets.length) continue;
      if (bullet.decision === "accept" || bullet.decision === "pending") {
        acceptedBullets.push(bullet.editedText ?? bulletText(diff.suggested_bullets[idx]));
      } else if (bullet.decision === "edit" && bullet.editedText) {
        acceptedBullets.push(bullet.editedText);
      } else {
        acceptedBullets.push(diff.original_bullets[idx] || bulletText(diff.suggested_bullets[idx]));
        rejectedIndices.push(idx);
      }
    }

    acceptedChanges[expId] = acceptedBullets;
    if (rejectedIndices.length > 0) {
      rejectedChanges[expId] = rejectedIndices;
    }
  }

  // Manual edits for education
  if (result.education_data) {
    for (const edu of result.education_data) {
      const achievements: string[] = [];
      if (edu.achievements) {
        for (let i = 0; i < edu.achievements.length; i++) {
          achievements.push(manualEdits[`achievement_${edu.id}_${i}`] || String(edu.achievements[i]));
        }
      }
      const modulesKey = `modules_${edu.id}`;
      const modules = manualEdits[modulesKey]
        ? manualEdits[modulesKey].split(",").map((m) => m.trim()).filter(Boolean)
        : edu.modules ?? [];
      acceptedChanges[`education_${edu.id}`] = { achievements, modules } as unknown;
    }
  }

  // Manual edits for skills
  if (result.skills_data) {
    for (const [category, skills] of Object.entries(result.skills_data)) {
      const key = `skills_${category}`;
      acceptedChanges[`skills_${category}`] = manualEdits[key]
        ? manualEdits[key].split(",").map((s) => s.trim()).filter(Boolean)
        : skills;
    }
  }

  return { acceptedChanges, rejectedChanges };
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function submitOverleafForm(latexContent: string) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "https://www.overleaf.com/docs";
  form.target = "_blank";
  const snip = document.createElement("input");
  snip.type = "hidden"; snip.name = "snip"; snip.value = latexContent;
  const name = document.createElement("input");
  name.type = "hidden"; name.name = "snip_name"; name.value = "cv.tex";
  form.append(snip, name);
  document.body.appendChild(form);
  form.submit();
  document.body.removeChild(form);
}

async function saveChanges(
  result: TailorResult,
  decisions: Record<string, Record<number, BulletState>>,
  manualEdits: Record<string, string>
) {
  const changes = buildChanges(result, decisions, manualEdits);
  await api.put(`/api/tailor/cv-versions/${result.cv_version_id}/accept-changes`, {
    accepted_changes: changes.acceptedChanges,
    rejected_changes: changes.rejectedChanges,
  });
}

export function useReviewExports(
  result: TailorResult | null,
  decisions: Record<string, Record<number, BulletState>>,
  manualEdits: Record<string, string>
) {
  const [saving, setSaving] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  /** Factory: wraps save + export action with shared loading/error state. */
  const makeExportHandler = useCallback(
    (action: (cvVersionId: string) => Promise<void>, errorMessage: string) =>
      async () => {
        if (!result) return;
        setSaving(true);
        setExportError(null);
        setSuccessMessage(null);
        try {
          await saveChanges(result, decisions, manualEdits);
          await action(result.cv_version_id);
        } catch {
          setExportError(errorMessage);
        } finally {
          setSaving(false);
        }
      },
    [result, decisions, manualEdits]
  );

  const handleDownloadPdf = useCallback(
    makeExportHandler(async (id) => {
      const { blob, filename } = await api.downloadFile(`/api/export/pdf/${id}`);
      triggerDownload(blob, filename || "cv.pdf");
    }, "PDF compilation failed. Try 'Open in Overleaf' instead."),
    [makeExportHandler]
  );

  const handleDownloadLatex = useCallback(
    makeExportHandler(async (id) => {
      const { blob, filename } = await api.downloadFile(`/api/export/latex/${id}`);
      triggerDownload(blob, filename || "cv.tex");
    }, "Failed to download LaTeX file."),
    [makeExportHandler]
  );

  const handleDownloadDocx = useCallback(
    makeExportHandler(async (id) => {
      const { blob, filename } = await api.downloadFilePost(`/api/export/docx/${id}`);
      triggerDownload(blob, filename || "cv.docx");
    }, "DOCX generation failed. Try downloading the PDF instead."),
    [makeExportHandler]
  );

  const handleOpenOverleaf = useCallback(
    makeExportHandler(async (id) => {
      const data = await api.post<{ success: boolean; latex_content: string }>(
        `/api/export/overleaf/${id}`
      );
      if (data.latex_content) {
        submitOverleafForm(data.latex_content);
      } else {
        throw new Error("no content");
      }
    }, "Failed to open Overleaf."),
    [makeExportHandler]
  );

  return {
    saving,
    exportError,
    successMessage,
    setSuccessMessage,
    setExportError,
    handleDownloadPdf,
    handleDownloadLatex,
    handleDownloadDocx,
    handleOpenOverleaf,
    clearExportError: () => setExportError(null),
    clearSuccessMessage: () => setSuccessMessage(null),
  };
}
