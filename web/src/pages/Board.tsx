import classnames from "classnames";

import { SQRT3 } from "../utils/coordinates";
import type { GameAction, GameState, TileCoordinate } from "../utils/api.types";
import { sameEdge, type BoardHighlight } from "../utils/boardTarget";
import Tile from "./Tile";
import Node from "./Node";
import Edge, { toEdgeId, type EdgeId } from "./Edge";
import Robber from "./Robber";

import "./Board.scss";

/**
 * This uses the formulas: W = SQRT3 * size and H = 2 * size.
 * Math comes from https://www.redblobgames.com/grids/hexagons/.
 */
function computeDefaultSize(divWidth: number, divHeight: number): number {
  const numLevels = 6; // 3 rings + 1/2 a tile for the outer water ring
  // divHeight = numLevels * (3h/4) + (h/4), implies:
  const maxSizeThatRespectsHeight = (4 * divHeight) / (3 * numLevels + 1) / 2;
  const correspondingWidth = SQRT3 * maxSizeThatRespectsHeight;
  let size: number;
  if (numLevels * correspondingWidth < divWidth) {
    // thus complete board would fit if we pick size based on height (height is limiting factor)
    size = maxSizeThatRespectsHeight;
  } else {
    // we'll have to decide size based on width.
    const maxSizeThatRespectsWidth = divWidth / numLevels / SQRT3;
    size = maxSizeThatRespectsWidth;
  }
  return size;
}

type BoardProps = {
  width: number;
  height: number;
  buildOnNodeClick: (
    id: number,
    action?: GameAction,
  ) => React.MouseEventHandler<HTMLDivElement>;
  buildOnEdgeClick: (
    id: [number, number],
    action?: GameAction,
  ) => React.MouseEventHandler<HTMLDivElement>;
  handleTileClick: (coordinate: TileCoordinate) => void;
  nodeActions?: Record<number, GameAction>;
  edgeActions?: Record<EdgeId, GameAction>;
  replayMode: boolean;
  gameState: GameState;
  isMobile: boolean;
  show: boolean;
  isMovingRobber: boolean;
  robberCoordinates?: Set<string>;
  highlight?: BoardHighlight;
};

export default function Board({
  width,
  height,
  buildOnNodeClick,
  buildOnEdgeClick,
  handleTileClick,
  nodeActions,
  edgeActions,
  replayMode,
  gameState,
  isMobile,
  show,
  isMovingRobber,
  robberCoordinates,
  highlight,
}: BoardProps) {
  // TODO: Keep in sync with CSS
  const containerHeight = height - 144 - 38 - 40;
  const containerWidth = isMobile ? width - 280 : width;
  const center: [number, number] = [containerWidth / 2, containerHeight / 2];
  const size = computeDefaultSize(containerWidth, containerHeight);
  if (!size) {
    return null;
  }

  const tiles = gameState.tiles.map(({ coordinate, tile }) => {
    const tileKey = `${coordinate}`;
    const spotlight = highlight?.tileKey === tileKey;
    return (
      <Tile
        key={tileKey}
        center={center}
        coordinate={coordinate}
        tile={tile}
        size={size}
        flashing={spotlight || !!robberCoordinates?.has(tileKey)}
        spotlight={spotlight}
        onClick={
          !isMovingRobber || robberCoordinates?.has(`${coordinate}`)
            ? () => handleTileClick(coordinate)
            : undefined
        }
      />
    );
  });
  const nodes = Object.values(gameState.nodes).map(
    ({ color, building, direction, tile_coordinate, id }) => {
      const spotlight = highlight?.nodeId === id;
      return (
        <Node
          key={id}
          center={center}
          size={size}
          coordinate={tile_coordinate}
          direction={direction}
          building={building}
          color={color}
          flashing={
            spotlight || (!replayMode && !!nodeActions && id in nodeActions)
          }
          spotlight={spotlight}
          onClick={buildOnNodeClick(
            id,
            nodeActions ? nodeActions[id] : undefined,
          )}
        />
      );
    },
  );
  const edges = Object.values(gameState.edges).map(
    ({ color, direction, tile_coordinate, id }) => {
      const spotlight = sameEdge(id, highlight?.edgeId ?? null);
      return (
        <Edge
          id={`${id[0]},${id[1]}`}
          key={`${id}`}
          center={center}
          size={size}
          coordinate={tile_coordinate}
          direction={direction}
          color={color}
          flashing={spotlight || (!!edgeActions && toEdgeId(id) in edgeActions)}
          spotlight={spotlight}
          onClick={buildOnEdgeClick(
            id,
            edgeActions ? edgeActions[toEdgeId(id)] : undefined,
          )}
        />
      );
    },
  );
  return (
    <div className={classnames("board", { show })}>
      {tiles}
      {edges}
      {nodes}
      <Robber
        center={center}
        size={size}
        coordinate={gameState.robber_coordinate}
      />
    </div>
  );
}
