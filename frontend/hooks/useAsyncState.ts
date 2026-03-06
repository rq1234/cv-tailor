"use client";

import { useCallback, useState } from "react";

/**
 * Shared loading/error state for async operations.
 * Wrap any async function with `run` to get automatic loading/error tracking.
 */
export function useAsyncState() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async <T>(
    fn: () => Promise<T>,
    errorMessage?: string,
  ): Promise<T | null> => {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      const msg = errorMessage ?? (err instanceof Error ? err.message : "An error occurred");
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, run };
}
