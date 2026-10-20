import { expect, test } from "vitest";

import { boardTarget, sameEdge } from "./boardTarget";

test("a settlement, road, or robber Action points at one board spot", () => {
  expect(boardTarget("BUILD_SETTLEMENT 29")).toEqual({
    nodeId: 29,
    edgeId: null,
    tileKey: null,
  });
  expect(boardTarget("BUILD_CITY 4")).toEqual({
    nodeId: 4,
    edgeId: null,
    tileKey: null,
  });
  expect(boardTarget("BUILD_ROAD (8, 27)")).toEqual({
    nodeId: null,
    edgeId: "8,27",
    tileKey: null,
  });
  expect(boardTarget("MOVE_ROBBER ((1, 0, -1), RED)")).toEqual({
    nodeId: null,
    edgeId: null,
    tileKey: "1,0,-1",
  });
  expect(boardTarget("ROLL")).toEqual({
    nodeId: null,
    edgeId: null,
    tileKey: null,
  });
  expect(sameEdge([27, 8], "8,27")).toBe(true);
  expect(sameEdge([8, 27], "8,27")).toBe(true);
  expect(sameEdge([1, 2], "8,27")).toBe(false);
});
