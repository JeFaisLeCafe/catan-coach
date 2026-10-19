export type PlayMode = "challenge" | "coach";

export function playModeStorageKey(gameId: string): string {
  return `catan-coach.playMode.${gameId}`;
}

export function loadPlayMode(gameId: string): PlayMode {
  return window.localStorage.getItem(playModeStorageKey(gameId)) === "coach"
    ? "coach"
    : "challenge";
}

export function savePlayMode(gameId: string, mode: PlayMode): void {
  window.localStorage.setItem(playModeStorageKey(gameId), mode);
}
