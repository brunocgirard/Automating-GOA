import { useCallback, useEffect, useState, type DependencyList } from "react";

interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useFetch<T>(
  fetcher: () => Promise<T>,
  deps: DependencyList = []
): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => {
    setReloadKey((value) => value + 1);
  }, []);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    void fetcher()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load data.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [reloadKey, ...deps]);

  return { data, loading, error, reload };
}
