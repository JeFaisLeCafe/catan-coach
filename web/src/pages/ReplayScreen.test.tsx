import { useContext } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { StateProvider, store } from "../store";
import { makeGameState } from "../test/fixtures";
import {
  getPositionLines,
  getReview,
  getState,
  startSearch,
  stopSearch,
} from "../utils/apiClient";
import type { PositionLines as PositionLinesReport } from "../utils/api.types";
import type { BlunderReport } from "../utils/api.types";
import ReplayScreen from "./ReplayScreen";

vi.mock("../utils/apiClient", () => ({
  getState: vi.fn(),
  getReview: vi.fn(),
  getPositionLines: vi.fn(),
  startSearch: vi.fn(),
  getSearch: vi.fn(),
  stopSearch: vi.fn(),
}));
vi.mock("./ZoomableBoard", () => ({
  default: ({ highlight }: { highlight?: { nodeId: number | null } }) => (
    <div data-testid="board">{highlight?.nodeId ?? "board"}</div>
  ),
}));
vi.mock("../components/LeftDrawer", () => ({
  default: () => <div>Players</div>,
}));
vi.mock("../components/RightDrawer", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <aside>{children}</aside>
  ),
}));
function StateIndexProbe() {
  const { state } = useContext(store);
  return (
    <output data-testid="state-index">{state.gameState?.state_index}</output>
  );
}

function renderReplayScreen() {
  return render(
    <StateProvider>
      <MemoryRouter initialEntries={["/replays/game-123"]}>
        <Routes>
          <Route path="/replays/:gameId" element={<ReplayScreen />} />
        </Routes>
      </MemoryRouter>
      <StateIndexProbe />
    </StateProvider>,
  );
}

const openingLines: PositionLinesReport = {
  seat: "RED",
  model: "vp-share(T=2.0)",
  fallback: true,
  notice:
    "These Actions tie on Win Probability. Listed by the hexes they touch.",
  forced: false,
  ordering: "tiles",
  win_probability: 0.333,
  played: "BUILD_SETTLEMENT 3",
  lines: [
    {
      action: "BUILD_SETTLEMENT 12",
      summary: "6 wheat · 9 wood · 5 ore, then road toward 8 brick",
      win_probability: 0.333,
      loss: 0,
      reasons: [],
    },
    {
      action: "BUILD_SETTLEMENT 3",
      summary: "2 wood · 11 brick, then road toward 4 sheep",
      win_probability: 0.333,
      loss: 0,
      reasons: [],
    },
  ],
};

const emptyReport: BlunderReport = {
  seat: "BLUE",
  model: "vp-share(T=2.0)",
  fallback: true,
  notice: null,
  search_budget: "immediate",
  complete: true,
  through_index: 12,
  head_index: 12,
  decisions: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getReview).mockResolvedValue(emptyReport);
  vi.mocked(getPositionLines).mockResolvedValue(openingLines);
  vi.mocked(getState).mockImplementation(async (_gameId, stateIndex) => {
    const index = stateIndex === "latest" ? 12 : Number(stateIndex);
    return makeGameState({ state_index: index });
  });
});

afterEach(() => {
  cleanup();
});

test("loads the latest replay boundary and navigates persisted states", async () => {
  const user = userEvent.setup();
  renderReplayScreen();

  expect(await screen.findByTestId("board")).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.getByText("Move: 0 / 12")).toBeInTheDocument();
  });
  expect(getState).toHaveBeenCalledWith("game-123", "latest");
  expect(getState).toHaveBeenCalledWith("game-123", 0);
  expect(screen.getByTestId("state-index")).toHaveTextContent("0");

  await user.click(screen.getByRole("button", { name: "Next Move" }));

  await waitFor(() => {
    expect(getState).toHaveBeenCalledWith("game-123", 1);
    expect(screen.getByTestId("state-index")).toHaveTextContent("1");
    expect(screen.getByText("Move: 1 / 12")).toBeInTheDocument();
  });
});

test("names the winner from the finished Position", async () => {
  vi.mocked(getState).mockImplementation(async (_gameId, stateIndex) =>
    makeGameState({
      state_index: stateIndex === "latest" ? 12 : Number(stateIndex),
      winning_color: stateIndex === "latest" ? "ORANGE" : null,
    }),
  );

  renderReplayScreen();

  expect(await screen.findByText("ORANGE")).toBeInTheDocument();
});

test("shows the lines for the position on the board", async () => {
  const user = userEvent.setup();
  renderReplayScreen();

  expect(
    await screen.findByText(/6 wheat · 9 wood · 5 ore/),
  ).toBeInTheDocument();
  expect(screen.getByText(/RED to move · best 33.3%/)).toBeInTheDocument();
  expect(
    screen.getByText(/Listed by the hexes they touch/),
  ).toBeInTheDocument();
  expect(screen.getByText("2 · played")).toBeInTheDocument();
  expect(getPositionLines).toHaveBeenCalledWith("game-123", 0);

  await user.click(screen.getByRole("button", { name: "Next Move" }));

  await waitFor(() => {
    expect(getPositionLines).toHaveBeenCalledWith("game-123", 1);
  });
});

test("opens a reviewed ply and sorts decisions by loss", async () => {
  const user = userEvent.setup();
  vi.mocked(getReview).mockResolvedValue({
    ...emptyReport,
    notice: "No trained model is available; using the vp-share Baseline.",
    decisions: [
      {
        ply: 4,
        seat: "BLUE",
        played: "BUILD_SETTLEMENT 3",
        best: "BUILD_SETTLEMENT 3",
        win_probability: 0.5,
        loss: 0,
        reasons: [],
        grade: "best",
      },
      {
        ply: 16,
        seat: "BLUE",
        played: "BUILD_SETTLEMENT 9",
        best: "BUILD_SETTLEMENT 8",
        win_probability: 0.3,
        loss: 0.2,
        reasons: [{ label: "production", delta: -0.2 }],
        grade: "blunder",
      },
    ],
  });

  renderReplayScreen();

  const blunder = await screen.findByRole("button", {
    name: /Ply 16/,
  });
  expect(blunder).toHaveClass("grade-blunder");
  expect(screen.getByText("Best BUILD_SETTLEMENT 8")).toBeInTheDocument();
  expect(
    screen.getByText(
      "No trained model is available; using the vp-share Baseline.",
    ),
  ).toBeInTheDocument();
  expect(screen.getByText(/search budget immediate/)).toBeInTheDocument();

  await user.click(blunder);
  await waitFor(() => {
    expect(getState).toHaveBeenCalledWith("game-123", 16);
    expect(screen.getByTestId("state-index")).toHaveTextContent("16");
  });

  await user.click(screen.getByRole("button", { name: "Loss" }));
  const rows = screen.getAllByRole("button", { name: /Ply / });
  expect(rows[0]).toHaveTextContent("Ply 16");
  expect(rows[1]).toHaveTextContent("Ply 4");
});

test("search keeps digging on every position until the position changes", async () => {
  const user = userEvent.setup();
  vi.mocked(startSearch).mockResolvedValue({
    job_id: "job-1",
    running: true,
    state_index: 0,
    source: "search",
    seat: "RED",
    model: "gbdt",
    fallback: false,
    notice: null,
    forced: false,
    simulations: 2,
    nodes: 6,
    elapsed: 1,
    horizon: 2,
    uncertainty: 0.01,
    lines: [
      {
        action: "BUILD_SETTLEMENT 12",
        win_probability: 0.4,
        loss: 0,
        visits: 2,
        reasons: [],
      },
    ],
  });

  renderReplayScreen();
  expect(
    await screen.findByText(/6 wheat · 9 wood · 5 ore/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("radio", { name: "5 seconds" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Start this budget" }),
  ).not.toBeInTheDocument();

  await waitFor(() => {
    expect(startSearch).toHaveBeenCalledWith(
      "game-123",
      expect.objectContaining({ mode: "continuous", state_index: 0 }),
    );
  });
  expect(screen.getByText(/2 simulations/)).toBeInTheDocument();
  expect(screen.getByText(/2 plies ahead/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();

  await user.hover(screen.getByText(/6 wheat · 9 wood · 5 ore/));
  expect(screen.getByTestId("board")).toHaveTextContent("12");
  await user.unhover(screen.getByText(/6 wheat · 9 wood · 5 ore/));
  expect(screen.getByTestId("board")).toHaveTextContent("board");

  await user.click(screen.getByRole("button", { name: "Next Move" }));

  await waitFor(() => {
    expect(stopSearch).toHaveBeenCalledWith("game-123", "job-1");
    expect(startSearch).toHaveBeenCalledWith(
      "game-123",
      expect.objectContaining({ mode: "continuous", state_index: 1 }),
    );
  });
});
