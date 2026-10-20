import { useEffect, useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { GridLoader } from "react-spinners";

import ZoomableBoard from "./ZoomableBoard";

import "./ReplayScreen.scss";
import LeftDrawer from "../components/LeftDrawer";
import RightDrawer from "../components/RightDrawer";
import { store } from "../store";
import ACTIONS from "../actions";
import { getPositionLines, getReview, getState } from "../utils/apiClient";
import ReplayBox from "../components/ReplayBox";
import PositionLines from "../components/PositionLines";
import ReviewPanel from "../components/ReviewPanel";
import type {
  BlunderReport,
  Color,
  PositionLines as PositionLinesReport,
} from "../utils/api.types";
import { applySearch } from "../utils/applySearch";
import { boardTarget } from "../utils/boardTarget";
import { useSearchStream } from "../hooks/useSearchStream";

function ReplayScreen() {
  const { gameId } = useParams();
  const { state, dispatch } = useContext(store);
  const [latestStateIndex, setLatestStateIndex] = useState<number>(0);
  const [stateIndex, setStateIndex] = useState<number>(0);
  const [winner, setWinner] = useState<Color | null>(null);
  const [report, setReport] = useState<BlunderReport | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [lines, setLines] = useState<PositionLinesReport | null>(null);
  const [linesError, setLinesError] = useState<string | null>(null);
  const [hoverAction, setHoverAction] = useState<string | null>(null);
  const { snapshot, stop, resume } = useSearchStream({
    gameId,
    enabled: Boolean(gameId),
    stateIndex,
  });
  const shownLines = lines && snapshot ? applySearch(lines, snapshot) : lines;

  const handlePrevState = () => setStateIndex((prev) => Math.max(prev - 1, 0));
  const handleNextState = () =>
    setStateIndex((prev) => Math.min(prev + 1, latestStateIndex));

  useEffect(() => {
    if (!gameId) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        let next = await getReview(gameId);
        while (!cancelled) {
          setReport(next);
          if (next.complete) {
            return;
          }
          const cursor = next.through_index;
          next = await getReview(gameId);
          if (next.through_index === cursor) {
            return;
          }
        }
      } catch {
        if (!cancelled) {
          setReviewError("The review stopped before this game was finished.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gameId]);

  useEffect(() => {
    if (!gameId) {
      return;
    }
    let cancelled = false;
    setLines(null);
    setLinesError(null);
    (async () => {
      try {
        const next = await getPositionLines(gameId, stateIndex);
        if (!cancelled) {
          setLines(next);
        }
      } catch {
        if (!cancelled) {
          setLinesError("This position could not be read.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gameId, stateIndex]);

  useEffect(() => {
    setHoverAction(null);
  }, [stateIndex]);

  useEffect(() => {
    if (!gameId) return;

    (async () => {
      const latestState = await getState(gameId, "latest");
      dispatch({ type: ACTIONS.SET_GAME_STATE, data: latestState });
      setLatestStateIndex(latestState.state_index);
      setWinner(latestState.winning_color);
    })();
  }, [gameId, dispatch]);

  useEffect(() => {
    if (!gameId) {
      return;
    }

    (async () => {
      const gameState = await getState(gameId, stateIndex);
      dispatch({ type: ACTIONS.SET_GAME_STATE, data: gameState });
    })();
  }, [gameId, stateIndex, dispatch]);

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
      {winner && (
        <p className="winner">
          Winner: <strong>{winner}</strong>
        </p>
      )}
      <ZoomableBoard replayMode={true} highlight={boardTarget(hoverAction)} />
      <LeftDrawer />
      <RightDrawer>
        <PositionLines
          lines={shownLines}
          error={linesError}
          snapshot={snapshot}
          onStop={stop}
          onResume={resume}
          onHoverAction={setHoverAction}
        />
        <ReviewPanel
          report={report}
          error={reviewError}
          onSelectPly={setStateIndex}
        />
        <ReplayBox
          stateIndex={stateIndex}
          latestStateIndex={latestStateIndex}
          onNextMove={handleNextState}
          onPrevMove={handlePrevState}
          onSeekMove={(index) => setStateIndex(index)}
        />
      </RightDrawer>
    </main>
  );
}

export default ReplayScreen;
