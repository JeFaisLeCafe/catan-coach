import { useCallback, useEffect, useRef, useState } from "react";

import type { SearchSnapshot } from "../utils/api.types";
import { getSearch, startSearch, stopSearch } from "../utils/apiClient";

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

export function useSearchStream({
  gameId,
  enabled,
  stateIndex,
}: {
  gameId: string | undefined;
  enabled: boolean;
  stateIndex: number | undefined;
}): { snapshot: SearchSnapshot | null; stop: () => void } {
  const [snapshot, setSnapshot] = useState<SearchSnapshot | null>(null);
  const held = useRef(false);
  const jobRef = useRef<string | undefined>(undefined);
  const gameRef = useRef(gameId);
  gameRef.current = gameId;

  const stop = useCallback(() => {
    held.current = true;
    setSnapshot((current) =>
      current ? { ...current, running: false } : current,
    );
    const jobId = jobRef.current;
    const currentGame = gameRef.current;
    if (currentGame && jobId) {
      void Promise.resolve(stopSearch(currentGame, jobId)).catch(
        () => undefined,
      );
    }
  }, []);

  useEffect(() => {
    if (!enabled || !gameId || stateIndex === undefined) {
      setSnapshot(null);
      return;
    }
    let cancelled = false;
    held.current = false;
    jobRef.current = undefined;
    setSnapshot(null);
    (async () => {
      try {
        const first = await startSearch(gameId, {
          mode: "continuous",
          state_index: stateIndex,
        });
        if (cancelled) {
          void Promise.resolve(stopSearch(gameId, first.job_id)).catch(
            () => undefined,
          );
          return;
        }
        jobRef.current = first.job_id;
        if (held.current) {
          void Promise.resolve(stopSearch(gameId, first.job_id)).catch(
            () => undefined,
          );
          setSnapshot({ ...first, running: false });
          return;
        }
        setSnapshot(first);
        let current = first;
        while (!cancelled && !held.current && current.running) {
          await wait(300);
          if (cancelled || held.current) {
            return;
          }
          const next = await getSearch(gameId);
          if (cancelled || held.current || next.job_id !== first.job_id) {
            return;
          }
          current = next;
          setSnapshot(next);
        }
      } catch {
        if (!cancelled) {
          setSnapshot(null);
        }
      }
    })();

    return () => {
      cancelled = true;
      const jobId = jobRef.current;
      if (jobId) {
        void Promise.resolve(stopSearch(gameId, jobId)).catch(() => undefined);
      }
    };
  }, [enabled, gameId, stateIndex]);

  return { snapshot, stop };
}
