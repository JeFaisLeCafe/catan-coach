import type { PositionLines, SearchSnapshot } from "./api.types";

export function applySearch(
  lines: PositionLines,
  snapshot: SearchSnapshot,
): PositionLines {
  const known = new Map(lines.lines.map((line) => [line.action, line]));
  const top = snapshot.lines.slice(0, 5);
  if (
    lines.played &&
    !top.some((line) => line.action === lines.played) &&
    snapshot.lines.some((line) => line.action === lines.played)
  ) {
    const played = snapshot.lines.find((line) => line.action === lines.played);
    if (played) {
      top.push(played);
    }
  }
  return {
    ...lines,
    seat: snapshot.seat,
    model: snapshot.model,
    fallback: snapshot.fallback,
    notice: snapshot.notice,
    forced: snapshot.forced,
    ordering: "win_probability",
    win_probability: top[0]?.win_probability ?? lines.win_probability,
    lines: top.map((line) => {
      const previous = known.get(line.action);
      return {
        action: line.action,
        summary: previous?.summary || line.summary || line.action,
        win_probability: line.win_probability,
        loss: line.loss,
        reasons: previous?.reasons ?? line.reasons,
      };
    }),
  };
}

export function formatSearchStatus(snapshot: SearchSnapshot): string {
  const uncertainty =
    snapshot.uncertainty > 0
      ? `±${(snapshot.uncertainty * 100).toFixed(1)}%`
      : "± —";
  return [
    `${snapshot.simulations} simulations`,
    `${snapshot.nodes} nodes`,
    `${snapshot.elapsed.toFixed(1)}s`,
    `${snapshot.horizon.toFixed(0)} plies ahead`,
    uncertainty,
  ].join(" · ");
}
