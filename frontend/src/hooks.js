import { useCallback, useEffect, useState } from "react";

// Loads data and exposes explicit loading / error / empty states. Re-runs when deps change; discards stale responses.
export function useLoad(fn, deps) {
  const [state, set] = useState({ loading: true, data: null, error: null });
  const run = useCallback(() => {
    let live = true;
    set((s) => ({ ...s, loading: true, error: null }));
    fn().then((data) => live && set({ loading: false, data, error: null }),
              (error) => live && set({ loading: false, data: null, error }));
    return () => { live = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(run, [run]);
  return { ...state, reload: run };
}
