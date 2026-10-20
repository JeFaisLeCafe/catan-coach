import { expect, test } from "vitest";

import { readableAction } from "./actions";

test("turns logged actions into sentences", () => {
  expect(readableAction("BUILD_SETTLEMENT 29")).toBe("Settlement 29");
  expect(readableAction("BUILD_ROAD (4, 15)")).toBe("Road 4–15");
  expect(readableAction("BUY_DEVELOPMENT_CARD")).toBe("Buy a development card");
  expect(
    readableAction("MARITIME_TRADE ('ORE', 'ORE', None, None, 'BRICK')"),
  ).toBe("Trade 2 ore for brick");
  expect(readableAction("MOVE_ROBBER ((1, 0, -1), C.ORANGE)")).toBe(
    "Move the robber, steal from Orange",
  );
});
