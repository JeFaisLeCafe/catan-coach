import { StrictMode, useContext } from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { StateProvider, store } from "../store";
import type { GameState } from "../utils/api.types";
import { getState, postAction } from "../utils/apiClient";
import { dispatchSnackbar } from "../components/Snackbar";
import { makeGameState } from "../test/fixtures";
import GameScreen from "./GameScreen";

const snackbar = vi.hoisted(() => ({
  enqueueSnackbar: vi.fn(),
  closeSnackbar: vi.fn(),
}));

vi.mock("../utils/apiClient", () => ({
  getState: vi.fn(),
  postAction: vi.fn(),
}));
vi.mock("../components/Snackbar", () => ({
  dispatchSnackbar: vi.fn(),
}));
vi.mock("notistack", () => ({
  useSnackbar: () => snackbar,
}));
vi.mock("./ZoomableBoard", () => ({
  default: () => <div data-testid="board">Board</div>,
}));

const theme = createTheme();
const baseState = makeGameState();

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function StateIndexProbe() {
  const { state } = useContext(store);
  return (
    <output data-testid="state-index">{state.gameState?.state_index}</output>
  );
}

function NavigationProbe() {
  const navigate = useNavigate();
  return (
    <>
      <button onClick={() => navigate("/games/game-456")}>Other game</button>
      <button onClick={() => navigate("/home")}>Home</button>
    </>
  );
}

function renderGameScreen({
  initialEntry = "/games/game-123",
  routePath = "/games/:gameId",
  replayMode = false,
  strictMode = false,
}: {
  initialEntry?: string;
  routePath?: string;
  replayMode?: boolean;
  strictMode?: boolean;
} = {}) {
  const screen = (
    <ThemeProvider theme={theme}>
      <StateProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <NavigationProbe />
          <Routes>
            <Route
              path={routePath}
              element={<GameScreen replayMode={replayMode} />}
            />
            <Route path="/replays/:gameId" element={<div>Replay</div>} />
            <Route path="/home" element={<div>Home page</div>} />
          </Routes>
        </MemoryRouter>
        <StateIndexProbe />
      </StateProvider>
    </ThemeProvider>
  );
  return render(strictMode ? <StrictMode>{screen}</StrictMode> : screen);
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

test("loads a persisted API state into the real gameplay controls", async () => {
  vi.mocked(getState).mockResolvedValue(baseState);

  renderGameScreen();

  expect(await screen.findByTestId("board")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "ROLL" })).toBeEnabled();
  expect(screen.getAllByTitle("Victory Points").length).toBeGreaterThan(0);
  expect(screen.getByTestId("state-index")).toHaveTextContent("12");
  expect(getState).toHaveBeenCalledWith("game-123", undefined);
  expect(postAction).not.toHaveBeenCalled();
});

test("advances a persisted bot turn and publishes the returned state", async () => {
  const botTurn = makeGameState({ current_color: "RED" });
  const humanTurn: GameState = makeGameState({
    state_index: 13,
    action_records: [
      [["RED", "END_TURN", null], null],
    ] as GameState["action_records"],
  });
  const actionResponse = deferred<GameState>();
  vi.mocked(getState).mockResolvedValue(botTurn);
  vi.mocked(postAction).mockReturnValue(actionResponse.promise);

  renderGameScreen({ strictMode: true });

  expect(await screen.findByTestId("board")).toBeInTheDocument();
  expect(postAction).toHaveBeenCalledWith("game-123");
  expect(postAction).toHaveBeenCalledOnce();

  vi.useFakeTimers();
  await act(async () => {
    actionResponse.resolve(humanTurn);
    await actionResponse.promise;
  });

  await act(async () => {
    await vi.runAllTimersAsync();
  });

  expect(screen.getByTestId("state-index")).toHaveTextContent("13");
  expect(screen.getByRole("button", { name: "ROLL" })).toBeEnabled();
  expect(dispatchSnackbar).toHaveBeenCalledOnce();
});

test("does not advance bot state retained from another game", async () => {
  vi.mocked(getState).mockResolvedValue(
    makeGameState({
      current_color: "RED",
      game: {
        id: "other-game",
        vps_to_win: 10,
        discard_limit: 7,
        friendly_robber: false,
      },
    }),
  );

  renderGameScreen();

  expect(await screen.findByTestId("board")).toBeInTheDocument();
  expect(postAction).not.toHaveBeenCalled();
});

test("does not publish a bot response after switching games", async () => {
  const botTurn = makeGameState({ current_color: "RED" });
  const oldGameResponse = makeGameState({ state_index: 13 });
  const newGameState = makeGameState({
    state_index: 21,
    game: {
      id: "game-456",
      vps_to_win: 10,
      discard_limit: 7,
      friendly_robber: false,
    },
  });
  vi.mocked(getState).mockImplementation(async (gameId) =>
    gameId === "game-456" ? newGameState : botTurn,
  );
  vi.mocked(postAction).mockResolvedValue(oldGameResponse);
  vi.useFakeTimers();

  renderGameScreen();
  await act(async () => Promise.resolve());
  expect(postAction).toHaveBeenCalledOnce();

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Other game" }));
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(screen.getByTestId("state-index")).toHaveTextContent("21");

  await act(async () => {
    await vi.runAllTimersAsync();
  });
  expect(screen.getByTestId("state-index")).toHaveTextContent("21");
});

test("does not publish a delayed bot response after leaving the game", async () => {
  vi.mocked(getState).mockResolvedValue(
    makeGameState({ current_color: "RED" }),
  );
  vi.mocked(postAction).mockResolvedValue(makeGameState({ state_index: 13 }));
  vi.useFakeTimers();

  renderGameScreen();
  await act(async () => Promise.resolve());
  expect(postAction).toHaveBeenCalledOnce();

  fireEvent.click(screen.getByRole("button", { name: "Home" }));
  expect(screen.getByText("Home page")).toBeInTheDocument();
  await act(async () => {
    await vi.runAllTimersAsync();
  });

  expect(screen.getByTestId("state-index")).toHaveTextContent("12");
});

test("loads a historical state without advancing bots in replay mode", async () => {
  vi.mocked(getState).mockResolvedValue(makeGameState({ state_index: 7 }));

  renderGameScreen({
    initialEntry: "/games/game-123/states/7",
    routePath: "/games/:gameId/states/:stateIndex",
    replayMode: true,
  });

  expect(await screen.findByTestId("board")).toBeInTheDocument();
  expect(screen.getByTestId("state-index")).toHaveTextContent("7");
  expect(getState).toHaveBeenCalledWith("game-123", "7");
  expect(postAction).not.toHaveBeenCalled();
  expect(
    screen.queryByRole("button", { name: "ROLL" }),
  ).not.toBeInTheDocument();
});

test("opens a finished game in replay", async () => {
  vi.mocked(getState).mockResolvedValue(
    makeGameState({ winning_color: "BLUE" }),
  );

  renderGameScreen();

  expect(await screen.findByText("Replay")).toBeInTheDocument();
  expect(postAction).not.toHaveBeenCalled();
});
