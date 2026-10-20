import type {
  PositionLines as PositionLinesReport,
  SearchSnapshot,
} from "../utils/api.types";
import SearchStatus from "./SearchStatus";

import "./PositionLines.scss";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function PositionLines({
  lines,
  error,
  snapshot,
  onStop,
  onHoverAction,
}: {
  lines: PositionLinesReport | null;
  error?: string | null;
  snapshot?: SearchSnapshot | null;
  onStop?: () => void;
  onHoverAction?: (action: string | null) => void;
}) {
  return (
    <section
      className={
        snapshot?.source === "search"
          ? "position-lines is-search"
          : "position-lines is-immediate"
      }
      aria-label="Position lines"
    >
      <h3>This position</h3>
      {snapshot && <SearchStatus snapshot={snapshot} onStop={onStop} />}
      {error && <p>{error}</p>}
      {!lines && !error && <p>Reading this position…</p>}
      {lines && lines.lines.length === 0 && <p>No legal Action.</p>}
      {lines && lines.lines.length > 0 && (
        <>
          <p className="position-meta">
            {`${lines.seat} to move · best ${formatPercent(lines.win_probability ?? 0)}`}
          </p>
          {lines.notice && <p className="position-notice">{lines.notice}</p>}
          {lines.forced && <p>This Action is forced</p>}
          <ol>
            {lines.lines.map((line, index) => {
              const played = line.action === lines.played;
              const rank = index < 5 ? index + 1 : null;
              return (
                <li
                  key={line.action}
                  className={played ? "is-played" : undefined}
                  onMouseEnter={() => onHoverAction?.(line.action)}
                  onMouseLeave={() => onHoverAction?.(null)}
                >
                  <span className="position-rank">
                    {rank ?? "Played"}
                    {played && rank !== null ? " · played" : ""}
                  </span>
                  <span>{line.summary || line.action}</span>
                  <span className="position-probability">
                    {formatPercent(line.win_probability)}
                    {line.loss > 0 ? ` · −${(line.loss * 100).toFixed(1)}` : ""}
                  </span>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
