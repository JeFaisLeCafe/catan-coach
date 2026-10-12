import cn from "classnames";

import "./PlayerStateBox.scss";
import { type Color, type PlayerState } from "../utils/api.types";
import ResourceCards from "./ResourceCards";

export default function PlayerStateBox({
  playerState,
  playerKey,
  color,
}: {
  playerState: PlayerState;
  playerKey: string;
  color: Color;
}) {
  const numberValue = (suffix: string) => {
    const value = playerState[`${playerKey}_${suffix}`];
    return typeof value === "number" ? value : 0;
  };
  const actualVps = numberValue(
    playerState[`${playerKey}_ACTUAL_VICTORY_POINTS`] === undefined
      ? "VICTORY_POINTS"
      : "ACTUAL_VICTORY_POINTS",
  );
  return (
    <div className={cn("player-state-box foreground", color)}>
      <ResourceCards playerState={playerState} playerKey={playerKey} />
      <div className="scores">
        <div
          className={cn("num-knights center-text", {
            bold: Boolean(playerState[`${playerKey}_HAS_ARMY`]),
          })}
          title="Knights Played"
        >
          <span>{numberValue("PLAYED_KNIGHT")}</span>
          <small>knights</small>
        </div>
        <div
          className={cn("num-roads center-text", {
            bold: Boolean(playerState[`${playerKey}_HAS_ROAD`]),
          })}
          title="Longest Road"
        >
          {numberValue("LONGEST_ROAD_LENGTH")}
          <small>roads</small>
        </div>
        <div
          className={cn("victory-points center-text", {
            bold: actualVps >= 10,
          })}
          title="Victory Points"
        >
          {actualVps}
          <small>VPs</small>
        </div>
      </div>
    </div>
  );
}
