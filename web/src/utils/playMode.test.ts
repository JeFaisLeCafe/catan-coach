import { afterEach, expect, test } from "vitest";

import { loadPlayMode, playModeStorageKey, savePlayMode } from "./playMode";

afterEach(() => {
  window.localStorage.clear();
});

test("defaults a new game to Challenge Mode", () => {
  expect(loadPlayMode("game-123")).toBe("challenge");
});

test("remembers Coach Mode for a game without treating it as a Ply", () => {
  savePlayMode("game-123", "coach");

  expect(window.localStorage.getItem(playModeStorageKey("game-123"))).toBe(
    "coach",
  );
  expect(loadPlayMode("game-123")).toBe("coach");
  expect(loadPlayMode("other-game")).toBe("challenge");
});
