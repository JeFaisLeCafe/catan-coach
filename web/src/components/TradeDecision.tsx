import { Button } from "@mui/material";

import type { Color, GameAction, GameState } from "../utils/api.types";
import { describeFreqdeck } from "../utils/trade";

function partner(action: GameAction): Color | null {
  if (action[1] !== "CONFIRM_TRADE") {
    return null;
  }
  const value = action[2][10];
  return typeof value === "string" ? value : null;
}

export default function TradeDecision({
  gameState,
  onAct,
}: {
  gameState: GameState;
  onAct: (action: GameAction) => void;
}) {
  const trade = gameState.current_trade ?? [];
  const offerer = gameState.colors[gameState.current_turn_index];
  const giving = describeFreqdeck(trade.slice(0, 5));
  const wanting = describeFreqdeck(trade.slice(5, 10));
  const accept = gameState.current_playable_actions.find(
    (action) => action[1] === "ACCEPT_TRADE",
  );
  const refuse = gameState.current_playable_actions.find(
    (action) => action[1] === "REJECT_TRADE",
  );
  const confirmations = gameState.current_playable_actions.filter(
    (action) => action[1] === "CONFIRM_TRADE",
  );
  const cancel = gameState.current_playable_actions.find(
    (action) => action[1] === "CANCEL_TRADE",
  );

  return (
    <div className="trade-decision">
      <p>
        {offerer} offers {giving} for {wanting}
      </p>
      {accept && <Button onClick={() => onAct(accept)}>Accept</Button>}
      {refuse && <Button onClick={() => onAct(refuse)}>Refuse</Button>}
      {confirmations.map((action) => (
        <Button key={partner(action)} onClick={() => onAct(action)}>
          {`Trade with ${partner(action)}`}
        </Button>
      ))}
      {cancel && <Button onClick={() => onAct(cancel)}>Cancel trade</Button>}
    </div>
  );
}
