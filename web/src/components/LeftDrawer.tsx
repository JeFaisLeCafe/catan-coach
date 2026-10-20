import React, { useCallback, useContext } from "react";
import cn from "classnames";
import SwipeableDrawer from "@mui/material/SwipeableDrawer";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";

import Hidden from "./Hidden";
import PlayerStateBox from "./PlayerStateBox";
import PlayModeToggle from "./PlayModeToggle";
import AnalysisPanel from "./AnalysisPanel";
import TimingSettings from "./TimingSettings";
import { humanizeActionRecord } from "../utils/promptUtils";
import { store } from "../store";
import ACTIONS from "../actions";
import { getHumanColor, playerKey } from "../utils/stateUtils";
import {
  type GameState,
  type LiveAnalysis,
  type SearchSnapshot,
} from "../utils/api.types";
import { type PlayMode } from "../utils/playMode";
import { isTabOrShift, type InteractionEvent } from "../utils/events";

import "./LeftDrawer.scss";

function SeatLabel({ gameState }: { gameState: GameState }) {
  const humanColor = getHumanColor(gameState);
  if (!humanColor) {
    return null;
  }
  return (
    <div
      className="perspective-toggle"
      title="Showing only what your seat can see"
    >
      Playing as {humanColor}
    </div>
  );
}

function DrawerContent({
  gameState,
  playMode,
  onPlayModeChange,
  analysis,
  snapshot,
  onStopSearch,
  onResumeSearch,
  onHoverAction,
  presentationDelay,
  onPresentationDelay,
}: {
  gameState: GameState;
  playMode?: PlayMode;
  onPlayModeChange?: (mode: PlayMode) => void;
  analysis?: LiveAnalysis | null;
  snapshot?: SearchSnapshot | null;
  onStopSearch?: () => void;
  onResumeSearch?: () => void;
  onHoverAction?: (action: string | null) => void;
  presentationDelay?: number;
  onPresentationDelay?: (milliseconds: number) => void;
}) {
  const playerSections = gameState.colors.map((color) => {
    const key = playerKey(gameState, color);
    return (
      <React.Fragment key={color}>
        <PlayerStateBox
          playerState={gameState.player_state}
          playerKey={key}
          color={color}
        />
        <Divider />
      </React.Fragment>
    );
  });

  return (
    <>
      {playMode && onPlayModeChange && (
        <PlayModeToggle mode={playMode} onChange={onPlayModeChange} />
      )}
      {presentationDelay !== undefined && onPresentationDelay && (
        <TimingSettings
          presentationDelay={presentationDelay}
          onPresentationDelay={onPresentationDelay}
        />
      )}
      <SeatLabel gameState={gameState} />
      {(analysis || snapshot) && (
        <AnalysisPanel
          analysis={analysis}
          snapshot={snapshot}
          onStop={onStopSearch}
          onResume={onResumeSearch}
          onHoverAction={onHoverAction}
        />
      )}
      {playerSections}
      <div className="log">
        {gameState.action_records
          .slice()
          .reverse()
          .map((actionRecord, i) => (
            <div
              key={i}
              className={cn("action foreground", actionRecord[0][0])}
            >
              {humanizeActionRecord(gameState, actionRecord)}
            </div>
          ))}
      </div>
    </>
  );
}

export default function LeftDrawer({
  playMode,
  onPlayModeChange,
  analysis,
  snapshot,
  onStopSearch,
  onResumeSearch,
  onHoverAction,
  presentationDelay,
  onPresentationDelay,
}: {
  playMode?: PlayMode;
  onPlayModeChange?: (mode: PlayMode) => void;
  analysis?: LiveAnalysis | null;
  snapshot?: SearchSnapshot | null;
  onStopSearch?: () => void;
  onResumeSearch?: () => void;
  onHoverAction?: (action: string | null) => void;
  presentationDelay?: number;
  onPresentationDelay?: (milliseconds: number) => void;
} = {}) {
  const { state, dispatch } = useContext(store);
  const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent);

  const openLeftDrawer = useCallback(
    (event: InteractionEvent) => {
      if (isTabOrShift(event)) {
        return;
      }

      dispatch({ type: ACTIONS.SET_LEFT_DRAWER_OPENED, data: true });
    },
    [dispatch],
  );
  const closeLeftDrawer = useCallback(
    (event: InteractionEvent) => {
      if (isTabOrShift(event)) {
        return;
      }

      dispatch({ type: ACTIONS.SET_LEFT_DRAWER_OPENED, data: false });
    },
    [dispatch],
  );

  return (
    <>
      <Hidden breakpoint={{ size: "md", direction: "up" }} implementation="js">
        <SwipeableDrawer
          className="left-drawer"
          anchor="left"
          open={state.isLeftDrawerOpen}
          onClose={closeLeftDrawer}
          onOpen={openLeftDrawer}
          disableBackdropTransition={!iOS}
          disableDiscovery={iOS}
          onKeyDown={closeLeftDrawer}
        >
          <DrawerContent
            gameState={state.gameState as GameState}
            playMode={playMode}
            onPlayModeChange={onPlayModeChange}
            analysis={analysis}
            snapshot={snapshot}
            onStopSearch={onStopSearch}
            onResumeSearch={onResumeSearch}
            onHoverAction={onHoverAction}
            presentationDelay={presentationDelay}
            onPresentationDelay={onPresentationDelay}
          />
        </SwipeableDrawer>
      </Hidden>
      <Hidden
        breakpoint={{ size: "sm", direction: "down" }}
        implementation="css"
      >
        <Drawer className="left-drawer" anchor="left" variant="permanent" open>
          <DrawerContent
            gameState={state.gameState as GameState}
            playMode={playMode}
            onPlayModeChange={onPlayModeChange}
            analysis={analysis}
            snapshot={snapshot}
            onStopSearch={onStopSearch}
            onResumeSearch={onResumeSearch}
            onHoverAction={onHoverAction}
            presentationDelay={presentationDelay}
            onPresentationDelay={onPresentationDelay}
          />
        </Drawer>
      </Hidden>
    </>
  );
}
