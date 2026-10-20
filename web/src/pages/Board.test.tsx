import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { makeGameState } from "../test/fixtures";
import Board from "./Board";

test("renders the nested tile, node, and edge shapes emitted by GameEncoder", () => {
  const gameState = makeGameState();

  const { container } = render(
    <Board
      width={1200}
      height={900}
      buildOnNodeClick={() => () => undefined}
      buildOnEdgeClick={() => () => undefined}
      handleTileClick={() => undefined}
      replayMode={false}
      gameState={gameState}
      isMobile={false}
      show
      isMovingRobber={false}
    />,
  );

  expect(container.querySelectorAll(".tile")).toHaveLength(3);
  expect(container.querySelectorAll(".node")).toHaveLength(1);
  expect(container.querySelectorAll(".edge")).toHaveLength(1);
  expect(container.querySelectorAll(".robber")).toHaveLength(1);
  expect(screen.getByText("11")).toBeInTheDocument();
  expect(screen.getByText("3:1")).toBeInTheDocument();
});

test("a hovered move marks that spot even in a replay", () => {
  const gameState = makeGameState();
  const props = {
    width: 1200,
    height: 900,
    buildOnNodeClick: () => () => undefined,
    buildOnEdgeClick: () => () => undefined,
    handleTileClick: () => undefined,
    replayMode: true,
    gameState,
    isMobile: false,
    show: true,
    isMovingRobber: false,
  };
  const { container, rerender } = render(
    <Board {...props} highlight={{ nodeId: 0, edgeId: null, tileKey: null }} />,
  );
  expect(container.querySelector(".node .pulse.spotlight")).not.toBeNull();

  rerender(
    <Board
      {...props}
      highlight={{ nodeId: null, edgeId: "1,0", tileKey: null }}
    />,
  );
  expect(container.querySelector(".edge .pulse.spotlight")).not.toBeNull();

  rerender(
    <Board
      {...props}
      highlight={{ nodeId: null, edgeId: null, tileKey: "0,0,0" }}
    />,
  );
  expect(container.querySelector(".tile.spotlight")).not.toBeNull();
});
