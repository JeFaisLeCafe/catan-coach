import axios from "axios";

import { API_URL } from "../configuration";
import type {
  BlunderReport,
  Color,
  GameAction,
  GameState,
  LiveAnalysis,
  PositionLines,
  SearchSnapshot,
} from "./api.types";

/** A registry key, e.g. "CATANATRON" or "AB". The server decides what exists. */
export type PlayerKey = string;

/** One settable parameter, as published by GET /api/players. */
export type PlayerParam = {
  name: string;
  type: "int" | "float" | "str" | "bool";
  default: number | string | boolean | null;
  /** Only present when the param declares a fixed set of values. */
  choices?: Array<string | number>;
  help: string;
};

export type PlayerEntry = {
  key: PlayerKey;
  name: string;
  description: string;
  is_bot: boolean;
  source: string;
  params: PlayerParam[];
};

export interface PlayerSpec {
  key: PlayerKey;
  params: Record<string, number | string | boolean | null>;
}

export type MapTemplate = "BASE" | "MINI" | "TOURNAMENT";
export type StateIndex = number | `${number}` | "latest";

export interface SavedGame {
  game_id: string;
  players: PlayerKey[];
  state_index: number;
  status: "in_progress" | "finished";
  winning_color: Color | null;
}

type CreateGameOptions = {
  players: PlayerSpec[];
  mapTemplate: MapTemplate;
  vpsToWin: number;
  discardLimit: number;
  friendlyRobber: boolean;
};

/** The players this server can seat. Replaces a hardcoded list in the UI. */
export async function getPlayers(): Promise<PlayerEntry[]> {
  const response = await axios.get<PlayerEntry[]>(API_URL + "/api/players");
  return response.data;
}

export async function getGames(): Promise<SavedGame[]> {
  const response = await axios.get<SavedGame[]>(API_URL + "/api/games");
  return response.data;
}

export async function createGame({
  players,
  mapTemplate,
  vpsToWin,
  discardLimit,
  friendlyRobber,
}: CreateGameOptions) {
  const response = await axios.post(API_URL + "/api/games", {
    players,
    map_template: mapTemplate,
    vps_to_win: vpsToWin,
    discard_limit: discardLimit,
    friendly_robber: friendlyRobber,
  });
  return response.data.game_id;
}

export async function getState(
  gameId: string,
  stateIndex: StateIndex = "latest",
): Promise<GameState> {
  const response = await axios.get(
    `${API_URL}/api/games/${gameId}/states/${stateIndex}`,
  );
  return response.data;
}

export async function getReview(gameId: string): Promise<BlunderReport> {
  const response = await axios.get<BlunderReport>(
    `${API_URL}/api/games/${gameId}/review`,
  );
  return response.data;
}

export async function getPositionLines(
  gameId: string,
  stateIndex: number,
): Promise<PositionLines> {
  const response = await axios.get<PositionLines>(
    `${API_URL}/api/games/${gameId}/states/${stateIndex}/analysis`,
  );
  return response.data;
}

export async function getAnalysis(gameId: string): Promise<LiveAnalysis> {
  const response = await axios.get<LiveAnalysis>(
    `${API_URL}/api/games/${gameId}/analysis`,
  );
  return response.data;
}

export async function startSearch(
  gameId: string,
  budget: {
    mode: "immediate" | "timed" | "continuous";
    seconds?: number;
    state_index: number;
  },
): Promise<SearchSnapshot> {
  const response = await axios.post<SearchSnapshot>(
    `${API_URL}/api/games/${gameId}/search`,
    budget,
  );
  return response.data;
}

export async function getSearch(gameId: string): Promise<SearchSnapshot> {
  const response = await axios.get<SearchSnapshot>(
    `${API_URL}/api/games/${gameId}/search`,
  );
  return response.data;
}

export async function stopSearch(
  gameId: string,
  jobId: string,
): Promise<SearchSnapshot> {
  const response = await axios.delete<SearchSnapshot>(
    `${API_URL}/api/games/${gameId}/search`,
    { params: { job: jobId } },
  );
  return response.data;
}

/** action=undefined means bot action */
export async function postAction(gameId: string, action?: GameAction) {
  const response = await axios.post<GameState>(
    `${API_URL}/api/games/${gameId}/actions`,
    action,
  );
  return response.data;
}
