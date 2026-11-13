/**
 * Generic data-fetching hook.
 * Wraps any async API call with loading / error / data state.
 * Refetches when the `deps` array changes.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const execute = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();
    setLoading(true);
    setError(null);
    fn()
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if ((err as { name?: string }).name === 'CanceledError') return;
        setError(err instanceof Error ? err.message : 'Unknown error');
        setData(null);
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    execute();
    return () => abortRef.current?.abort();
  }, [execute]);

  return { data, loading, error, refetch: execute };
}
