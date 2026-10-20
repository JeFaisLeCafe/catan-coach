import { expect, test } from "vitest";

import { reasonHint, reasonName } from "./reasons";

test("names the model groups in plain language", () => {
  expect(reasonName("points")).toBe("Victory points");
  expect(reasonName("hand")).toBe("Cards in hand");
  expect(reasonName("reachable expansion")).toBe("Room to build");
});

test("says whether a reason raised or lowered the chance", () => {
  expect(reasonHint({ label: "hand", delta: 0.2 })).toContain(
    "raised the chance",
  );
  expect(reasonHint({ label: "points", delta: -0.1 })).toContain(
    "lowered the chance",
  );
});
