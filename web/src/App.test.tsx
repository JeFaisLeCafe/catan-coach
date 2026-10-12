import { afterEach, test, expect, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import App from "./App";

afterEach(cleanup);

vi.mock("./utils/apiClient", async (importOriginal) => ({
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
      params: [],
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
}));

test("renders setup controls on the home page", () => {
  const { getByText } = render(<App />);
  expect(getByText(/Map Template/i)).toBeInTheDocument();
  expect(getByText(/Points to Win/i)).toBeInTheDocument();
  expect(getByText(/Card Discard Limit/i)).toBeInTheDocument();
  expect(getByText(/Open hands. Random discard choice./i)).toBeInTheDocument();
  expect(getByText(/^Players$/i)).toBeInTheDocument();
  expect(getByText(/^Start$/i)).toBeInTheDocument();
});

test("offers to continue a saved game", async () => {
  const { findByText } = render(<App />);

  expect(await findByText("Continue")).toBeInTheDocument();
  expect(await findByText(/12 Actions/)).toBeInTheDocument();
});
