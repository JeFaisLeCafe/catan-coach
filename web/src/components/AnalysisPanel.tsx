import type { LiveAnalysis, SearchSnapshot } from "../utils/api.types";
import SearchStatus from "./SearchStatus";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function AnalysisPanel({
  analysis,
  snapshot,
  onStop,
  onHoverAction,
}: {
  analysis?: LiveAnalysis | null;
  snapshot?: SearchSnapshot | null;
  onStop?: () => void;
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
        win_probability: line.win_probability,
        loss: line.loss,
        reasons: line.reasons,
      }))
    : (analysis?.actions ?? []);
  const searching = snapshot?.source === "search";

  return (
    <section
      className={
        searching ? "analysis-panel is-search" : "analysis-panel is-immediate"
      }
      aria-label="Live Analysis"
    >
      {notice && <p className="analysis-notice">{notice}</p>}
      <p className="analysis-meta">{`Seat ${seat} · ${model}`}</p>
      {snapshot ? (
        <SearchStatus snapshot={snapshot} onStop={onStop} />
      ) : (
        <p className="search-status is-immediate">Model</p>
      )}
      {forced && <p className="analysis-forced">This Action is forced</p>}
      <ol className="analysis-actions">
        {rows.map((row) => (
          <li
            key={row.action}
            onMouseEnter={() => onHoverAction?.(row.action)}
            onMouseLeave={() => onHoverAction?.(null)}
          >
            <div>{`${row.action} ${formatPercent(row.win_probability)}`}</div>
            {row.loss > 0 && (
              <div className="analysis-loss">
                {`−${(row.loss * 100).toFixed(1)}`}
              </div>
            )}
            {row.reasons.map((reason) => (
              <div key={reason.label} className="analysis-reason">
                {reason.label}
              </div>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}
