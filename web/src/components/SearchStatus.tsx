import type { SearchSnapshot } from "../utils/api.types";
import { formatSearchStatus } from "../utils/applySearch";

import "./SearchStatus.scss";

export default function SearchStatus({
  snapshot,
  onStop,
  onResume,
}: {
  snapshot: SearchSnapshot;
  onStop?: () => void;
  onResume?: () => void;
}) {
  const label = snapshot.running
    ? "Searching"
    : onResume
      ? "Paused"
      : snapshot.source === "search"
        ? "Search finished"
        : "First look";

  return (
    <div className="search-status-row">
      <div className="search-status-copy">
        <p className="search-kicker">{label}</p>
        <p
          className={
            snapshot.source === "search"
              ? "search-status is-search"
              : "search-status is-immediate"
          }
        >
          {formatSearchStatus(snapshot)}
        </p>
      </div>
      {snapshot.running && onStop && (
        <button type="button" className="stop-search" onClick={onStop}>
          Stop
        </button>
      )}
      {!snapshot.running && onResume && (
        <button type="button" className="stop-search" onClick={onResume}>
          Resume
        </button>
      )}
    </div>
  );
}
