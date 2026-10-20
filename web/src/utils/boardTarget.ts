export interface BoardHighlight {
  nodeId: number | null;
  edgeId: string | null;
  tileKey: string | null;
}

const EMPTY: BoardHighlight = { nodeId: null, edgeId: null, tileKey: null };

const NODE = /^(?:BUILD_SETTLEMENT|BUILD_CITY) (\d+)$/;
const EDGE = /^BUILD_ROAD \((-?\d+), (-?\d+)\)$/;
const TILE = /^MOVE_ROBBER \(\((-?\d+), (-?\d+), (-?\d+)\)/;

export function boardTarget(action: string | null): BoardHighlight {
  if (!action) {
    return EMPTY;
  }
  const node = NODE.exec(action);
  if (node) {
    return { nodeId: Number(node[1]), edgeId: null, tileKey: null };
  }
  const edge = EDGE.exec(action);
  if (edge) {
    return { nodeId: null, edgeId: `${edge[1]},${edge[2]}`, tileKey: null };
  }
  const tile = TILE.exec(action);
  if (tile) {
    return {
      nodeId: null,
      edgeId: null,
      tileKey: `${tile[1]},${tile[2]},${tile[3]}`,
    };
  }
  return EMPTY;
}

export function sameEdge(
  id: readonly [number, number],
  edgeId: string | null,
): boolean {
  if (edgeId === null) {
    return false;
  }
  return edgeId === `${id[0]},${id[1]}` || edgeId === `${id[1]},${id[0]}`;
}
