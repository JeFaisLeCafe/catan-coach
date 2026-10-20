const RESOURCE: Record<string, string> = {
  WOOD: "wood",
  BRICK: "brick",
  SHEEP: "sheep",
  WHEAT: "wheat",
  ORE: "ore",
};

function resource(name: string): string {
  return RESOURCE[name] ?? name.toLowerCase();
}

function seatName(name: string): string {
  return `${name[0]}${name.slice(1).toLowerCase()}`;
}

export function readableAction(action: string): string {
  if (action === "END_TURN") {
    return "End turn";
  }
  if (action === "ROLL") {
    return "Roll";
  }
  if (action === "BUY_DEVELOPMENT_CARD") {
    return "Buy a development card";
  }
  const settlement = /^BUILD_SETTLEMENT (\d+)$/.exec(action);
  if (settlement) {
    return `Settlement ${settlement[1]}`;
  }
  const city = /^BUILD_CITY (\d+)$/.exec(action);
  if (city) {
    return `City ${city[1]}`;
  }
  const road = /^BUILD_ROAD \((-?\d+), (-?\d+)\)$/.exec(action);
  if (road) {
    return `Road ${road[1]}–${road[2]}`;
  }
  const robber = /^MOVE_ROBBER \(.+, C\.([A-Z]+)\)$/.exec(action);
  if (robber) {
    return `Move the robber, steal from ${seatName(robber[1])}`;
  }
  if (action.startsWith("MOVE_ROBBER")) {
    return "Move the robber";
  }
  const trade = /^MARITIME_TRADE \((.*)\)$/.exec(action);
  if (trade) {
    const parts = [...trade[1].matchAll(/'([A-Z]+)'|None/g)].map(
      (match) => match[1] ?? null,
    );
    const received = parts[parts.length - 1];
    const given = parts
      .slice(0, -1)
      .filter((part): part is string => part !== null);
    if (received && given.length > 0) {
      const counts = new Map<string, number>();
      for (const item of given) {
        counts.set(item, (counts.get(item) ?? 0) + 1);
      }
      const offer = [...counts.entries()]
        .map(([item, count]) => `${count} ${resource(item)}`)
        .join(" and ");
      return `Trade ${offer} for ${resource(received)}`;
    }
  }
  return action;
}
