import type {
  PositionLines as PositionLinesReport,
  SearchSnapshot,
} from "../utils/api.types";
import ReasonList from "./ReasonList";
import SearchStatus from "./SearchStatus";

import "./coach.scss";
import "./PositionLines.scss";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function PositionLines({
  lines,
  error,
  snapshot,
  onStop,
  onResume,
  onHoverAction,
}: {
  lines: PositionLinesReport | null;
  error?: string | null;
  snapshot?: SearchSnapshot | null;
  onStop?: () => void;
  onResume?: () => void;
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
      <header className="panel-heading">
        <h3>This position</h3>
        <p>Hover a move to find it on the board.</p>
      </header>
      {snapshot && (
        <SearchStatus snapshot={snapshot} onStop={onStop} onResume={onResume} />
      )}
      {error && <p className="panel-error">{error}</p>}
      {!lines && !error && <p>Reading this position…</p>}
      {lines && lines.lines.length === 0 && <p>No legal move.</p>}
      {lines && lines.lines.length > 0 && (
        <>
          <p className="position-meta">
            {`${lines.seat} to move · best ${formatPercent(lines.win_probability ?? 0)}`}
          </p>
          {lines.notice && <p className="position-notice">{lines.notice}</p>}
          {lines.forced && <p>This move is the only legal one.</p>}
          <ol>
            {lines.lines.map((line, index) => {
              const played = line.action === lines.played;
              const rank = index < 5 ? index + 1 : null;
              return (
                <li
                  key={line.action}
                  className={played ? "move-card is-played" : "move-card"}
                  onMouseEnter={() => onHoverAction?.(line.action)}
                  onMouseLeave={() => onHoverAction?.(null)}
                >
                  <div className="move-card-top">
                    <span className="position-rank">
                      {rank ?? "Played"}
                      {played && rank !== null ? " · played" : ""}
                    </span>
                    <span className="position-probability">
                      {formatPercent(line.win_probability)}
                    </span>
                  </div>
                  <span className="move-summary">
                    {line.summary || line.action}
                  </span>
                  <span
                    className="chance"
                    aria-hidden="true"
                    style={{
                      ["--chance" as string]: `${Math.max(4, line.win_probability * 100)}%`,
                    }}
                  />
                  {line.loss > 0 && (
                    <span className="move-loss">
                      {`${(line.loss * 100).toFixed(1)} points behind the best`}
                    </span>
                  )}
                  <ReasonList reasons={line.reasons} />
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
