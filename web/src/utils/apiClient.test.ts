import { beforeEach, expect, test, vi } from "vitest";

import {
  createGame,
  getAnalysis,
  getGames,
  getPositionLines,
  getReview,
  getState,
  postAction,
} from "./apiClient";
import { makeGameState } from "../test/fixtures";

const http = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("axios", () => ({ default: http }));

beforeEach(() => {
  vi.clearAllMocks();
});

test("uses the local game API contract", async () => {
  const state = makeGameState();
  http.get
    .mockResolvedValueOnce({ data: [{ game_id: "game-123" }] })
    .mockResolvedValueOnce({ data: state });
  http.post.mockResolvedValueOnce({ data: state });

  await expect(getGames()).resolves.toEqual([{ game_id: "game-123" }]);
  await expect(getState("game-123")).resolves.toBe(state);
  await expect(postAction("game-123", ["BLUE", "ROLL", null])).resolves.toBe(
    state,
  );

  expect(http.get).toHaveBeenNthCalledWith(1, "/api/games");
  expect(http.get).toHaveBeenNthCalledWith(
    2,
    "/api/games/game-123/states/latest",
  );
  expect(http.post).toHaveBeenCalledWith("/api/games/game-123/actions", [
    "BLUE",
    "ROLL",
    null,
  ]);
});

test("loads live Analysis without posting an Action", async () => {
  const analysis = {
    seat: "BLUE",
    model: "vp-share(T=2.0)",
    fallback: true,
    notice: "No trained model is available; using the vp-share Baseline.",
    forced: false,
    actions: [
      {
        action: "ROLL",
        win_probability: 0.42,
        loss: 0,
        reasons: [{ label: "production", delta: 0.01 }],
      },
    ],
  };
  http.get.mockResolvedValueOnce({ data: analysis });

  await expect(getAnalysis("game-123")).resolves.toEqual(analysis);
  expect(http.get).toHaveBeenCalledWith("/api/games/game-123/analysis");
  expect(http.post).not.toHaveBeenCalled();
});

test("loads the lines for one replay Position", async () => {
  const lines = {
    seat: "RED",
    model: "vp-share(T=2.0)",
    fallback: true,
    notice: null,
    forced: false,
    ordering: "tiles",
    win_probability: 0.33,
    played: null,
    lines: [],
  };
  http.get.mockResolvedValueOnce({ data: lines });

  await expect(getPositionLines("game-123", 0)).resolves.toEqual(lines);
  expect(http.get).toHaveBeenCalledWith(
    "/api/games/game-123/states/0/analysis",
  );
  expect(http.post).not.toHaveBeenCalled();
});

test("loads a Blunder Report without posting an Action", async () => {
  const report = {
    seat: "BLUE",
    model: "vp-share(T=2.0)",
    fallback: true,
    notice: null,
    search_budget: "immediate",
    complete: true,
    through_index: 2,
    head_index: 2,
    decisions: [],
  };
  http.get.mockResolvedValueOnce({ data: report });

  await expect(getReview("game-123")).resolves.toEqual(report);
  expect(http.get).toHaveBeenCalledWith("/api/games/game-123/review");
  expect(http.post).not.toHaveBeenCalled();
});

test("translates browser setup options for game creation", async () => {
  http.post.mockResolvedValue({ data: { game_id: "new-game" } });

  await expect(
    createGame({
      players: [
        { key: "HUMAN", params: {} },
        { key: "CATANATRON", params: { depth: 3 } },
      ],
      mapTemplate: "BASE",
      vpsToWin: 10,
      discardLimit: 7,
      friendlyRobber: false,
    }),
  ).resolves.toBe("new-game");

  expect(http.post).toHaveBeenCalledWith("/api/games", {
    players: [
      { key: "HUMAN", params: {} },
      { key: "CATANATRON", params: { depth: 3 } },
    ],
    map_template: "BASE",
    vps_to_win: 10,
    discard_limit: 7,
    friendly_robber: false,
  });
});
