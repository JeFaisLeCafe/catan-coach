import type { LiveAnalysis } from "../utils/api.types";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function AnalysisPanel({
  analysis,
}: {
  analysis: LiveAnalysis;
}) {
  return (
    <section className="analysis-panel" aria-label="Live Analysis">
      {analysis.notice && <p className="analysis-notice">{analysis.notice}</p>}
      <p className="analysis-meta">
        Seat {analysis.seat} · {analysis.model}
      </p>
      {analysis.forced && (
        <p className="analysis-forced">This Action is forced</p>
      )}
      <ol className="analysis-actions">
        {analysis.actions.map((row) => (
          <li key={row.action}>
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
