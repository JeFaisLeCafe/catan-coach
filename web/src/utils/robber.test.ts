import { expect, test } from "vitest";

import type { MoveRobberAction } from "./api.types";
import { robberActionsForTile } from "./robber";

const blue: MoveRobberAction = ["RED", "MOVE_ROBBER", [[0, 0, 0], "BLUE"]];
const orange: MoveRobberAction = ["RED", "MOVE_ROBBER", [[0, 0, 0], "ORANGE"]];
const otherHex: MoveRobberAction = ["RED", "MOVE_ROBBER", [[1, -1, 0], "BLUE"]];

test("keeps every player who can be robbed on the chosen hex", () => {
  expect(
    robberActionsForTile([blue, orange, otherHex], [0, 0, 0]),
  ).toEqual([blue, orange]);
});
