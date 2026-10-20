import type { SearchSnapshot } from "../utils/api.types";
import { formatSearchStatus } from "../utils/applySearch";

import "./SearchStatus.scss";

export default function SearchStatus({
  snapshot,
  onStop,
}: {
  snapshot: SearchSnapshot;
  onStop?: () => void;
}) {
  return (
    <div className="search-status-row">
      <p
        className={
          snapshot.source === "search"
            ? "search-status is-search"
            : "search-status is-immediate"
        }
      >
        {snapshot.source === "search" ? "Search" : "Model"}
        {" · "}
        {formatSearchStatus(snapshot)}
      </p>
      {snapshot.running && onStop && (
        <button type="button" className="stop-search" onClick={onStop}>
          Stop
        </button>
      )}
    </div>
  );
}
