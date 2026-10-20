import { expect, test } from "vitest";

import type { PositionLines, SearchSnapshot } from "./api.types";
import { applySearch, formatSearchStatus } from "./applySearch";
import { budgetRequest } from "./searchBudget";

const lines: PositionLines = {
  seat: "RED",
  model: "vp-share(T=2.0)",
  fallback: true,
  notice: null,
  forced: false,
  ordering: "tiles",
  win_probability: 0.3,
  played: "BUILD_SETTLEMENT 3",
  lines: [
    {
      action: "BUILD_SETTLEMENT 12",
      summary: "6 wheat",
      win_probability: 0.3,
      loss: 0,
      reasons: [],
    },
    {
      action: "BUILD_SETTLEMENT 3",
      summary: "2 wood",
      win_probability: 0.3,
      loss: 0,
      reasons: [{ label: "production", delta: 0.1 }],
    },
  ],
};

const snapshot: SearchSnapshot = {
  job_id: "job-1",
  running: false,
  state_index: 0,
  source: "search",
  seat: "RED",
  model: "gbdt",
  fallback: false,
  notice: null,
  forced: false,
  simulations: 2,
  nodes: 4,
  elapsed: 0.5,
  horizon: 1.5,
  uncertainty: 0.02,
  lines: [
    {
      action: "BUILD_SETTLEMENT 12",
      win_probability: 0.44,
      loss: 0,
      visits: 2,
      reasons: [],
    },
    {
      action: "BUILD_SETTLEMENT 3",
      win_probability: 0.2,
      loss: 0.24,
      visits: 1,
      reasons: [],
    },
    {
      action: "BUILD_SETTLEMENT 20",
      summary: "6 ore",
      win_probability: 0.1,
      loss: 0.34,
      visits: 1,
      reasons: [],
    },
  ],
};

test("search keeps the position summary and the played Action", () => {
  const merged = applySearch(lines, snapshot);

  expect(merged.lines[0]).toMatchObject({
    action: "BUILD_SETTLEMENT 12",
    summary: "6 wheat",
    win_probability: 0.44,
  });
  expect(merged.lines[1].reasons).toEqual([
    { label: "production", delta: 0.1 },
  ]);
  expect(merged.lines[2]).toMatchObject({
    action: "BUILD_SETTLEMENT 20",
    summary: "6 ore",
  });
  expect(merged.played).toBe("BUILD_SETTLEMENT 3");
  expect(formatSearchStatus(snapshot)).toContain("2 plies ahead");
  expect(formatSearchStatus(snapshot)).not.toContain("depth");
  expect(formatSearchStatus(snapshot)).not.toContain("±");
});

test("timed presets become a duration and continuous does not", () => {
  expect(budgetRequest({ preset: "5", seconds: 10 })).toEqual({
    mode: "timed",
    seconds: 5,
  });
  expect(budgetRequest({ preset: "120", seconds: 10 })).toEqual({
    mode: "timed",
    seconds: 120,
  });
  expect(budgetRequest({ preset: "continuous", seconds: 10 })).toEqual({
    mode: "continuous",
  });
});
