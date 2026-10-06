import { useCallback, useEffect, useRef, useState } from "react";
import { isCancelled } from "./api/client";

/** A synchronous guard prevents rapid duplicate clicks before React renders disabled controls. */
export function useTask() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const active = useRef<AbortController | null>(null);
  useEffect(
    () => () => {
      active.current?.abort();
    },
    [],
  );
  const run = useCallback(
    async <T>(
      operation: (signal: AbortSignal) => Promise<T>,
    ): Promise<T | undefined> => {
      if (active.current) return undefined;
      const controller = new AbortController();
      active.current = controller;
      setBusy(true);
      setError(null);
      try {
        const result = await operation(controller.signal);
        return controller.signal.aborted ? undefined : result;
      } catch (failure) {
        if (!isCancelled(failure) && !controller.signal.aborted)
          setError(failure);
      } finally {
        if (!controller.signal.aborted) {
          active.current = null;
          setBusy(false);
        }
      }
    },
    [],
  );
  return { busy, error, run, clearError: () => setError(null) };
}

export function useQuery<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    data?: T;
    loading: boolean;
    error: unknown;
  }>({ loading: true, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, error: null });
    load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ data, loading: false, error: null });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setState({ loading: false, error });
      });
    return () => controller.abort();
  }, [load, revision]);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  return { ...state, reload };
}
