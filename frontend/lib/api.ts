/**
 * Typed fetch wrapper for FastAPI backend.
 *
 * Automatically retries on network errors (e.g. Render cold-start connection
 * refused) with exponential backoff before surfacing an error to the caller.
 */

import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Typed error thrown by every api.* method.
 * Callers can `instanceof ApiError` and read `.status` to distinguish
 * 4xx user errors (e.g. 409 in-flight conflict) from 5xx server errors.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Timeout per attempt — long enough to survive a Render cold start (~60s). */
const REQUEST_TIMEOUT_MS = 90_000;

/** How long to wait between retry attempts (ms). */
const RETRY_DELAYS_MS = [8_000, 20_000]; // 2 retries → 3 attempts total

const getAuthHeaders = async (): Promise<Record<string, string>> => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

async function request<T>(
  path: string,
  options?: RequestInit,
  _attemptIndex = 0,
): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
        ...options?.headers,
      },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Server took too long to respond — please try again");
    }
    // Network error (e.g. connection refused during cold start) — retry
    const delay = RETRY_DELAYS_MS[_attemptIndex];
    if (delay !== undefined) {
      await new Promise((resolve) => setTimeout(resolve, delay));
      return request<T>(path, options, _attemptIndex + 1);
    }
    throw new Error("Server is starting up — please wait a moment and try again");
  } finally {
    clearTimeout(timeoutId);
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(error.detail || `Request failed: ${res.status}`, res.status);
  }

  return res.json();
}

/** Shared multipart upload helper — avoids duplicating fetch + error handling. */
async function _uploadFile<T>(
  path: string,
  file: File,
  _attemptIndex = 0,
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);

  const authHeaders = await getAuthHeaders();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      body: formData,
      headers: authHeaders,
    });
  } catch {
    const delay = RETRY_DELAYS_MS[_attemptIndex];
    if (delay !== undefined) {
      await new Promise((resolve) => setTimeout(resolve, delay));
      return _uploadFile<T>(path, file, _attemptIndex + 1);
    }
    throw new Error("Server is starting up — please wait a moment and try again");
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(error.detail || `Upload failed: ${res.status}`, res.status);
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

  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
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
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(error.detail || `Download failed: ${res.status}`, res.status);
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
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(error.detail || `Stream failed: ${res.status}`, res.status);
    }

    return res;
  },
};
