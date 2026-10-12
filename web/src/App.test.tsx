import { afterEach, test, expect, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { createGame } from "./utils/apiClient";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.history.pushState({}, "", "/");
});

vi.mock("./utils/apiClient", async (importOriginal) => {
  const { makeGameState } = await import("./test/fixtures");
  return {
    ...(await importOriginal<typeof import("./utils/apiClient")>()),
    getPlayers: vi.fn().mockResolvedValue([
      {
        key: "HUMAN",
        name: "Human",
        description: "",
        is_bot: false,
        source: "catanatron",
        params: [],
      },
      {
        key: "CATANATRON",
        name: "Catanatron",
        description: "",
        is_bot: true,
        source: "catanatron",
        params: [
          {
            name: "depth",
            type: "int",
            default: 2,
            help: "Search depth",
          },
        ],
      },
    ]),
    getGames: vi.fn().mockResolvedValue([
      {
        game_id: "saved-game",
        players: ["HUMAN", "CATANATRON"],
        state_index: 12,
        status: "in_progress",
        winning_color: null,
      },
    ]),
    createGame: vi.fn().mockResolvedValue("new-game"),
    getState: vi.fn().mockResolvedValue(makeGameState()),
    postAction: vi.fn(),
  };
});

test("renders setup controls on the home page", () => {
  const { getByText } = render(<App />);
  expect(getByText(/Map Template/i)).toBeInTheDocument();
  expect(getByText(/Points to Win/i)).toBeInTheDocument();
  expect(getByText(/Card Discard Limit/i)).toBeInTheDocument();
  expect(getByText(/Open hands. Random discard choice./i)).toBeInTheDocument();
  expect(getByText(/^Players$/i)).toBeInTheDocument();
  expect(getByText(/^Start$/i)).toBeInTheDocument();
  expect(getByText("3/4")).toBeInTheDocument();
});

test("offers to continue a saved game", async () => {
  const { findByText } = render(<App />);

  expect(await findByText("Continue")).toBeInTheDocument();
  expect(await findByText(/12 Actions/)).toBeInTheDocument();
});

test("starts three seats with configurable bot strength", async () => {
  const user = userEvent.setup();
  vi.mocked(createGame).mockImplementationOnce(
    () => new Promise<string>(() => undefined),
  );
  const { findAllByLabelText, findByRole } = render(<App />);
  const [firstBotDepth] = await findAllByLabelText("depth");

  await user.clear(firstBotDepth);
  await user.type(firstBotDepth, "4");
  await user.click(await findByRole("button", { name: "Start" }));

  expect(createGame).toHaveBeenCalledWith(
    expect.objectContaining({
      players: [
        { key: "HUMAN", params: {} },
        { key: "CATANATRON", params: { depth: 4 } },
        { key: "CATANATRON", params: {} },
      ],
    }),
  );
});

test("recovers when game creation fails", async () => {
  const user = userEvent.setup();
  vi.mocked(createGame).mockRejectedValueOnce(new Error("invalid settings"));
  const { findByRole, findByText } = render(<App />);

  await user.click(await findByRole("button", { name: "Start" }));

  expect(
    await findByText("Could not start the game. Check the player settings."),
  ).toBeInTheDocument();
  expect(await findByRole("button", { name: "Start" })).toBeEnabled();
});
