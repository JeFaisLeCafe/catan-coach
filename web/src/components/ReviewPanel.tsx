import { useMemo, useState } from "react";

import type { BlunderReport, DecisionGrade } from "../utils/api.types";

import "./ReviewPanel.scss";

const GRADE_LABEL: Record<DecisionGrade, string> = {
  best: "Best",
  "near-tie": "Near-tie",
  mistake: "Mistake",
  blunder: "Blunder",
};

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function ReviewPanel({
  report,
  error,
  onSelectPly,
}: {
  report: BlunderReport | null;
  error?: string | null;
  onSelectPly: (ply: number) => void;
}) {
  const [byLoss, setByLoss] = useState(false);
  const decisions = useMemo(() => {
    const rows = report?.decisions ?? [];
    if (!byLoss) {
      return rows;
    }
    return [...rows].sort(
      (left, right) => right.loss - left.loss || left.ply - right.ply,
    );
  }, [byLoss, report]);

  return (
    <section className="review-panel" aria-label="Blunder Report">
      <h3>Review</h3>
      {error && <p>{error}</p>}
      {!report && !error && <p>Reviewing decisions…</p>}
      {report && (
        <>
          {report.notice && <p className="review-notice">{report.notice}</p>}
          <p className="review-meta">
            {report.model} · search budget {report.search_budget}
            {!report.complete && " · reviewing…"}
          </p>
          <div className="review-sort">
            <button
              type="button"
              aria-pressed={!byLoss}
              onClick={() => setByLoss(false)}
            >
              Time
            </button>
            <button
              type="button"
              aria-pressed={byLoss}
              onClick={() => setByLoss(true)}
            >
              Loss
            </button>
          </div>
          {report.complete && decisions.length === 0 && (
            <p>No choices to review.</p>
          )}
          <ol className="review-decisions">
            {decisions.map((decision) => (
              <li key={decision.ply}>
                <button
                  type="button"
                  className={`review-decision grade-${decision.grade}`}
                  onClick={() => onSelectPly(decision.ply)}
                >
                  <span>{`Ply ${decision.ply}`}</span>
                  <span className="review-grade">
                    {GRADE_LABEL[decision.grade]}
                  </span>
                  <span>{decision.played}</span>
                  <span>
                    {`${formatPercent(decision.win_probability)} · −${(decision.loss * 100).toFixed(1)}`}
                  </span>
                  {decision.loss > 0 && (
                    <span className="review-best">{`Best ${decision.best}`}</span>
                  )}
                  {decision.reasons.map((reason) => (
                    <span key={reason.label} className="review-reason">
                      {reason.label}
                    </span>
                  ))}
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
