import { useMemo, useState } from "react";

import { readableAction } from "../utils/actions";
import type { BlunderReport, DecisionGrade } from "../utils/api.types";
import ReasonList from "./ReasonList";

import "./coach.scss";
import "./ReviewPanel.scss";

const GRADE_LABEL: Record<DecisionGrade, string> = {
  best: "Best",
  "near-tie": "Close",
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
    <section className="review-panel" aria-label="Your choices">
      <header className="panel-heading">
        <h3>Your choices</h3>
        <p>
          A saved first look at each move you made. Open one to put it on the
          board.
        </p>
      </header>
      {error && <p className="panel-error">{error}</p>}
      {!report && !error && <p>Reading your choices…</p>}
      {report && (
        <>
          {report.notice && <p className="review-notice">{report.notice}</p>}
          {!report.complete && (
            <p className="review-meta">Still reading the rest of the game.</p>
          )}
          <div className="review-sort" role="group" aria-label="Sort choices">
            <button
              type="button"
              aria-pressed={!byLoss}
              onClick={() => setByLoss(false)}
            >
              In order
            </button>
            <button
              type="button"
              aria-pressed={byLoss}
              onClick={() => setByLoss(true)}
            >
              Costliest
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
                  <span className="review-kicker">
                    <span>{`Ply ${decision.ply}`}</span>
                    <span className="review-grade">
                      {GRADE_LABEL[decision.grade]}
                    </span>
                  </span>
                  <span className="review-played">
                    {readableAction(decision.played)}
                  </span>
                  <span className="review-score">
                    {formatPercent(decision.win_probability)}
                    {decision.loss > 0
                      ? ` · ${(decision.loss * 100).toFixed(1)} points behind`
                      : ""}
                  </span>
                  {decision.loss > 0 && (
                    <span className="review-best">{`Preferred ${readableAction(decision.best)}`}</span>
                  )}
                  <ReasonList reasons={decision.reasons} />
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
