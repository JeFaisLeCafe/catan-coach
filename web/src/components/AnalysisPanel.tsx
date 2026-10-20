import type { LiveAnalysis, SearchSnapshot } from "../utils/api.types";
import ReasonList from "./ReasonList";
import SearchStatus from "./SearchStatus";

import "./coach.scss";
import "./AnalysisPanel.scss";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function AnalysisPanel({
  analysis,
  snapshot,
  onStop,
  onResume,
  onHoverAction,
}: {
  analysis?: LiveAnalysis | null;
  snapshot?: SearchSnapshot | null;
  onStop?: () => void;
  onResume?: () => void;
  onHoverAction?: (action: string | null) => void;
}) {
  const seat = snapshot?.seat || analysis?.seat;
  const model = snapshot?.model || analysis?.model;
  const notice = snapshot?.notice ?? analysis?.notice ?? null;
  const forced = snapshot?.forced ?? analysis?.forced ?? false;
  if (!seat || !model) {
    return null;
  }
  const rows = snapshot
    ? snapshot.lines.map((line) => ({
        action: line.action,
        summary: line.summary,
        win_probability: line.win_probability,
        loss: line.loss,
        reasons: line.reasons,
      }))
    : (analysis?.actions ?? []).map((row) => ({ ...row, summary: undefined }));
  const best = rows[0]?.win_probability ?? 0;

  return (
    <section className="analysis-panel" aria-label="Live Analysis">
      <header className="panel-heading">
        <h3>This position</h3>
        <p>Hover a move to find it on the board.</p>
      </header>
      {notice && <p className="analysis-notice">{notice}</p>}
      <p className="analysis-meta">{`Seat ${seat} · ${model}`}</p>
      {snapshot ? (
        <SearchStatus snapshot={snapshot} onStop={onStop} onResume={onResume} />
      ) : (
        <p className="search-status is-immediate">First look from the model</p>
      )}
      {forced && (
        <p className="analysis-forced">This move is the only legal one.</p>
      )}
      <ol className="analysis-actions">
        {rows.map((row) => {
          const reading = `${row.action} ${formatPercent(row.win_probability)}`;
          const width =
            best > 0
              ? (row.win_probability / best) * 100
              : row.win_probability * 100;
          return (
            <li
              key={row.action}
              className="move-card"
              onMouseEnter={() => onHoverAction?.(row.action)}
              onMouseLeave={() => onHoverAction?.(null)}
            >
              {row.summary && row.summary !== row.action && (
                <span className="move-summary">{row.summary}</span>
              )}
              <span className="move-action">{reading}</span>
              <span
                className="chance"
                aria-hidden="true"
                style={{ ["--chance" as string]: `${Math.max(6, width)}%` }}
              />
              {row.loss > 0 && (
                <div className="analysis-loss">
                  {`${(row.loss * 100).toFixed(1)} points behind the best`}
                </div>
              )}
              <ReasonList reasons={row.reasons} />
            </li>
          );
        })}
      </ol>
    </section>
  );
}
