import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { GridLoader } from "react-spinners";
import { useSnackbar } from "notistack";

import ZoomableBoard from "./ZoomableBoard";
import ActionsToolbar from "./ActionsToolbar";

import "./GameScreen.scss";
import LeftDrawer from "../components/LeftDrawer";
import { store } from "../store";
import ACTIONS from "../actions";
import {
  type StateIndex,
  getAnalysis,
  getState,
  postAction,
} from "../utils/apiClient";
import { dispatchSnackbar } from "../components/Snackbar";
import { getHumanColor } from "../utils/stateUtils";
import type { LiveAnalysis } from "../utils/api.types";
import { loadPlayMode, savePlayMode, type PlayMode } from "../utils/playMode";
import { useSearchStream } from "../hooks/useSearchStream";
import { boardTarget } from "../utils/boardTarget";
import {
  loadPresentationDelay,
  savePresentationDelay,
} from "../utils/searchBudget";

// postAction already waits for the bot's real computation. Presentation Delay
// only pauses the picture of that Action.

function GameScreen({ replayMode }: { replayMode: boolean }) {
  const { gameId, stateIndex } = useParams();
  const navigate = useNavigate();
  const { state, dispatch } = useContext(store);
  const { enqueueSnackbar, closeSnackbar } = useSnackbar();
  const [isBotThinking, setIsBotThinking] = useState(false);
  const [playMode, setPlayMode] = useState<PlayMode>("challenge");
  const [analysis, setAnalysis] = useState<LiveAnalysis | null>(null);
  const [hoverAction, setHoverAction] = useState<string | null>(null);
  const [presentationDelay, setPresentationDelay] = useState(
    loadPresentationDelay,
  );
  const botRequest = useRef<{ gameId: string } | null>(null);
  const activeGameId = useRef(gameId);

  useEffect(() => {
    activeGameId.current = gameId;
    return () => {
      if (activeGameId.current === gameId) {
        activeGameId.current = undefined;
      }
      if (botRequest.current?.gameId === gameId) {
        botRequest.current = null;
      }
    };
  }, [gameId]);

  useEffect(() => {
    if (!gameId || replayMode) {
      setPlayMode("challenge");
      setAnalysis(null);
      return;
    }
    setPlayMode(loadPlayMode(gameId));
    setAnalysis(null);
  }, [gameId, replayMode]);

  const changePlayMode = useCallback(
    (mode: PlayMode) => {
      if (!gameId) {
        return;
      }
      setPlayMode(mode);
      savePlayMode(gameId, mode);
      if (mode === "challenge") {
        setAnalysis(null);
      }
    },
    [gameId],
  );

  const changePresentationDelay = useCallback((milliseconds: number) => {
    const next = Number.isFinite(milliseconds)
      ? Math.min(5000, Math.max(0, milliseconds))
      : 300;
    setPresentationDelay(next);
    savePresentationDelay(next);
  }, []);

  const coach = !replayMode && playMode === "coach";
  const { snapshot, stop, resume } = useSearchStream({
    gameId,
    enabled:
      coach &&
      state.gameState?.game.id === gameId &&
      !state.gameState?.winning_color,
    stateIndex: state.gameState?.state_index,
  });

  useEffect(() => {
    setHoverAction(null);
  }, [state.gameState?.state_index]);

  useEffect(() => {
    if (
      !gameId ||
      replayMode ||
      playMode !== "coach" ||
      !state.gameState ||
      state.gameState.game.id !== gameId ||
      state.gameState.winning_color
    ) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const result = await getAnalysis(gameId);
        if (!cancelled) {
          setAnalysis(result);
        }
      } catch {
        if (!cancelled) {
          setAnalysis(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gameId, replayMode, playMode, state.gameState]);

  useEffect(() => {
    if (!gameId) {
      return;
    }

    let cancelled = false;
    (async () => {
      const gameState = await getState(gameId, stateIndex as StateIndex);
      if (!cancelled) {
        dispatch({ type: ACTIONS.SET_GAME_STATE, data: gameState });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gameId, stateIndex, dispatch]);

  useEffect(() => {
    if (
      gameId &&
      !replayMode &&
      state.gameState?.game.id === gameId &&
      state.gameState?.winning_color !== null &&
      state.gameState?.winning_color !== undefined
    ) {
      navigate(`/replays/${gameId}`, { replace: true });
    }
  }, [
    gameId,
    navigate,
    replayMode,
    state.gameState?.game.id,
    state.gameState?.winning_color,
  ]);

  useEffect(() => {
    if (
      !state.gameState ||
      state.gameState.game.id !== gameId ||
      replayMode ||
      !gameId ||
      botRequest.current?.gameId === gameId
    ) {
      return;
    }
    if (
      state.gameState.bot_colors.includes(state.gameState.current_color) &&
      !state.gameState.winning_color
    ) {
      const request = { gameId };
      botRequest.current = request;
      const finishRequest = () => {
        if (botRequest.current === request) {
          botRequest.current = null;
          setIsBotThinking(false);
        }
      };
      (async () => {
        setIsBotThinking(true);
        try {
          const gameState = await postAction(gameId);
          if (activeGameId.current !== gameId) {
            finishRequest();
            return;
          }
          setTimeout(() => {
            if (
              activeGameId.current !== gameId ||
              botRequest.current !== request
            ) {
              finishRequest();
              return;
            }
            finishRequest();
            dispatch({ type: ACTIONS.SET_GAME_STATE, data: gameState });
            if (getHumanColor(gameState)) {
              dispatchSnackbar(enqueueSnackbar, closeSnackbar, gameState);
            }
          }, presentationDelay);
        } catch {
          finishRequest();
        }
      })();
    }
  }, [
    gameId,
    replayMode,
    state.gameState,
    dispatch,
    enqueueSnackbar,
    closeSnackbar,
    presentationDelay,
  ]);

  if (!state.gameState) {
    return (
      <main>
        <GridLoader className="loader" color="#000000" size={100} />
      </main>
    );
  }

  return (
    <main>
      <h1 className="logo">Catan Coach</h1>
      <ZoomableBoard
        replayMode={replayMode}
        highlight={boardTarget(hoverAction)}
      />
      <ActionsToolbar isBotThinking={isBotThinking} replayMode={replayMode} />
      <LeftDrawer
        playMode={replayMode ? undefined : playMode}
        onPlayModeChange={replayMode ? undefined : changePlayMode}
        analysis={replayMode || playMode !== "coach" ? null : analysis}
        snapshot={replayMode || playMode !== "coach" ? null : snapshot}
        onStopSearch={stop}
        onResumeSearch={resume}
        onHoverAction={setHoverAction}
        presentationDelay={replayMode ? undefined : presentationDelay}
        onPresentationDelay={replayMode ? undefined : changePresentationDelay}
      />
    </main>
  );
}

export default GameScreen;
