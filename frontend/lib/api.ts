/**
 * Typed fetch wrapper for FastAPI backend.
 */

import { supabase } from "@/lib/supabase";
import { useAuthStore } from "@/store/authStore";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const getAuthHeaders = async (): Promise<Record<string, string>> => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const handleAuthFailure = (status: number) => {
  if (status === 401) {
    // Clear auth state; AuthProvider will redirect via Next.js router.
    // This avoids a hard page reload and lets the component show the error first.
    useAuthStore.setState({ user: null, session: null });
  }
};

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
  });

  if (!res.ok) {
    handleAuthFailure(res.status);
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

/** Shared multipart upload helper — avoids duplicating fetch + error handling. */
async function _uploadFile<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);

  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    body: formData,
    headers: authHeaders,
  });

  if (!res.ok) {
    handleAuthFailure(res.status);
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string) =>
    request<T>(path, { method: "DELETE" }),

  upload: <T>(path: string, file: File): Promise<T> =>
    _uploadFile<T>(path, file),

  uploadScreenshot: (file: File): Promise<{ extracted_text: string }> =>
    _uploadFile<{ extracted_text: string }>("/api/applications/screenshot", file),

  /** Download a file as a Blob (for PDF/DOCX/LaTeX exports). */
  downloadFile: async (
    path: string,
    method: "GET" | "POST" = "POST"
  ): Promise<{ blob: Blob; filename: string }> => {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_URL}${path}`, { method, headers: authHeaders });

    if (!res.ok) {
      handleAuthFailure(res.status);
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `Download failed: ${res.status}`);
    }

    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || "download";
    return { blob, filename };
  },

  /** Open an SSE stream. Returns the raw Response for manual reading. */
  stream: async (path: string, body?: unknown): Promise<Response> => {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      handleAuthFailure(res.status);
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `Stream failed: ${res.status}`);
    }

    return res;
  },
};
