import { expect, test } from "vitest";

import { describeFreqdeck, emptyCounts, offerIsValid, offerTradeAction } from "./trade";

test("rejects an offer that gives nothing, asks nothing, or swaps the same resource", () => {
  const giving = { ...emptyCounts(), WOOD: 1 };
  const receiving = { ...emptyCounts(), BRICK: 1 };

  expect(offerIsValid(emptyCounts(), receiving)).toBe(false);
  expect(offerIsValid(giving, emptyCounts())).toBe(false);
  expect(offerIsValid({ ...giving, BRICK: 1 }, receiving)).toBe(false);
  expect(offerIsValid(giving, receiving)).toBe(true);
});

test("encodes an offer as the engine's ten-count freqdeck", () => {
  expect(
    offerTradeAction(
      "BLUE",
      { ...emptyCounts(), WOOD: 1 },
      { ...emptyCounts(), ORE: 2 },
    ),
  ).toEqual(["BLUE", "OFFER_TRADE", [1, 0, 0, 0, 0, 0, 0, 0, 0, 2]]);
});

test("describes only the resources in a freqdeck", () => {
  expect(describeFreqdeck([1, 0, 0, 0, 2])).toBe("1 WOOD, 2 ORE");
});
