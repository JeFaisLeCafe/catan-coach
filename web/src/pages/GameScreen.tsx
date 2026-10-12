import { useContext, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { GridLoader } from "react-spinners";
import { useSnackbar } from "notistack";

import ZoomableBoard from "./ZoomableBoard";
import ActionsToolbar from "./ActionsToolbar";

import "./GameScreen.scss";
import LeftDrawer from "../components/LeftDrawer";
import { store } from "../store";
import ACTIONS from "../actions";
import { type StateIndex, getState, postAction } from "../utils/apiClient";
import { dispatchSnackbar } from "../components/Snackbar";
import { getHumanColor } from "../utils/stateUtils";

// Visual pacing only; postAction already waits for the bot's real computation.
const BOT_PRESENTATION_DELAY_MS = 300;

function GameScreen({ replayMode }: { replayMode: boolean }) {
  const { gameId, stateIndex } = useParams();
  const navigate = useNavigate();
  const { state, dispatch } = useContext(store);
  const { enqueueSnackbar, closeSnackbar } = useSnackbar();
  const [isBotThinking, setIsBotThinking] = useState(false);
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
          }, BOT_PRESENTATION_DELAY_MS);
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
      <ZoomableBoard replayMode={replayMode} />
      <ActionsToolbar isBotThinking={isBotThinking} replayMode={replayMode} />
      <LeftDrawer />
    </main>
  );
}

export default GameScreen;
