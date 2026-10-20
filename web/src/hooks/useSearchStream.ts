import { useCallback, useEffect, useRef, useState } from "react";

import type { SearchSnapshot } from "../utils/api.types";
import {
  getSearch,
  resumeSearch,
  startSearch,
  stopSearch,
} from "../utils/apiClient";

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
}): {
  snapshot: SearchSnapshot | null;
  stop: () => void;
  resume: (() => void) | undefined;
} {
  const [snapshot, setSnapshot] = useState<SearchSnapshot | null>(null);
  const [paused, setPaused] = useState(false);
  const held = useRef(false);
  const jobRef = useRef<string | undefined>(undefined);
  const gameRef = useRef(gameId);
  const stateIndexRef = useRef(stateIndex);
  const generation = useRef(0);
  gameRef.current = gameId;
  stateIndexRef.current = stateIndex;

  const poll = useCallback(async (game: string, jobId: string, gen: number) => {
    while (generation.current === gen && !held.current) {
      await wait(300);
      if (generation.current !== gen || held.current) {
        return;
      }
      const next = await getSearch(game);
      if (generation.current !== gen || held.current || next.job_id !== jobId) {
        return;
      }
      setSnapshot(next);
      if (!next.running) {
        return;
      }
    }
  }, []);

  const stop = useCallback(() => {
    held.current = true;
    setPaused(true);
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

  const resume = useCallback(() => {
    const currentGame = gameRef.current;
    const jobId = jobRef.current;
    const index = stateIndexRef.current;
    if (!currentGame || !jobId || index === undefined) {
      return;
    }
    held.current = false;
    setPaused(false);
    setSnapshot((current) =>
      current ? { ...current, running: true } : current,
    );
    const gen = ++generation.current;
    void (async () => {
      try {
        const next = await resumeSearch(currentGame, jobId);
        if (generation.current !== gen || held.current) {
          if (generation.current === gen && held.current) {
            void Promise.resolve(stopSearch(currentGame, jobId)).catch(
              () => undefined,
            );
          }
          return;
        }
        jobRef.current = next.job_id;
        setSnapshot(next);
        await poll(currentGame, next.job_id, gen);
      } catch {
        if (generation.current !== gen || held.current) {
          return;
        }
        try {
          const first = await startSearch(currentGame, {
            mode: "continuous",
            state_index: index,
          });
          if (generation.current !== gen || held.current) {
            void Promise.resolve(
              stopSearch(currentGame, first.job_id, { cancel: true }),
            ).catch(() => undefined);
            return;
          }
          jobRef.current = first.job_id;
          setSnapshot(first);
          await poll(currentGame, first.job_id, gen);
        } catch {
          if (generation.current === gen) {
            setSnapshot(null);
          }
        }
      }
    })();
  }, [poll]);

  useEffect(() => {
    if (!enabled || !gameId || stateIndex === undefined) {
      setSnapshot(null);
      setPaused(false);
      return;
    }
    const gen = ++generation.current;
    held.current = false;
    setPaused(false);
    jobRef.current = undefined;
    setSnapshot(null);
    (async () => {
      try {
        const first = await startSearch(gameId, {
          mode: "continuous",
          state_index: stateIndex,
        });
        if (generation.current !== gen) {
          void Promise.resolve(
            stopSearch(gameId, first.job_id, { cancel: true }),
          ).catch(() => undefined);
          return;
        }
        jobRef.current = first.job_id;
        if (held.current) {
          void Promise.resolve(stopSearch(gameId, first.job_id)).catch(
            () => undefined,
          );
          setSnapshot({ ...first, running: false });
          setPaused(true);
          return;
        }
        setSnapshot(first);
        await poll(gameId, first.job_id, gen);
      } catch {
        if (generation.current === gen) {
          setSnapshot(null);
        }
      }
    })();

    return () => {
      generation.current += 1;
      const jobId = jobRef.current;
      if (jobId) {
        void Promise.resolve(stopSearch(gameId, jobId, { cancel: true })).catch(
          () => undefined,
        );
      }
    };
  }, [enabled, gameId, poll, stateIndex]);

  return { snapshot, stop, resume: paused ? resume : undefined };
}
