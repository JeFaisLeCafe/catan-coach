import { beforeEach, expect, test, vi } from "vitest";

import { createGame, getGames, getState, postAction } from "./apiClient";
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
