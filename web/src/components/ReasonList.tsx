import type { AnalysisReason } from "../utils/api.types";
import { reasonHint, reasonName } from "../utils/reasons";

import "./ReasonList.scss";

export default function ReasonList({ reasons }: { reasons: AnalysisReason[] }) {
  if (reasons.length === 0) {
    return null;
  }
  return (
    <ul className="reason-list">
      {reasons.map((reason) => (
        <li
          key={reason.label}
          className={
            reason.delta > 0
              ? "is-up"
              : reason.delta < 0
                ? "is-down"
                : undefined
          }
          title={reasonHint(reason)}
        >
          {reasonName(reason.label)}
        </li>
      ))}
    </ul>
  );
}
