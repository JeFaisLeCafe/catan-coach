import type { GameAction, MoveRobberAction, TileCoordinate } from "./api.types";

export function robberActionsForTile(
  actions: GameAction[],
  coordinate: TileCoordinate,
): MoveRobberAction[] {
  return actions.filter(
    (action): action is MoveRobberAction =>
      action[1] === "MOVE_ROBBER" &&
      action[2][0].every((value, index) => value === coordinate[index]),
  );
}
