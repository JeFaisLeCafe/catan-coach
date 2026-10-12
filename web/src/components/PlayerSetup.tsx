import { Button, Checkbox, MenuItem, Select, TextField } from "@mui/material";

import type {
  PlayerEntry,
  PlayerKey,
  PlayerParam,
  PlayerSpec,
} from "../utils/apiClient";

interface PlayerSetupProps {
  color: string;
  index: number;
  player: PlayerSpec;
  available: PlayerEntry[];
  humanKeys: Set<PlayerKey>;
  humanCount: number;
  canRemove: boolean;
  onPlayerChange: (key: PlayerKey) => void;
  onParamChange: (
    name: string,
    value: number | string | boolean | null,
  ) => void;
  onRemove: () => void;
}

function parseValue(param: PlayerParam, value: string) {
  if (value === "") {
    return null;
  }
  if (param.type === "int") {
    return Number.parseInt(value, 10);
  }
  if (param.type === "float") {
    return Number.parseFloat(value);
  }
  return value;
}

export default function PlayerSetup({
  color,
  index,
  player,
  available,
  humanKeys,
  humanCount,
  canRemove,
  onPlayerChange,
  onParamChange,
  onRemove,
}: PlayerSetupProps) {
  const selected = available.find((option) => option.key === player.key);
  const isHuman = (key: PlayerKey) => humanKeys.has(key);
  const paramValue = (param: PlayerParam) =>
    Object.prototype.hasOwnProperty.call(player.params, param.name)
      ? player.params[param.name]
      : param.default;

  return (
    <div className="player-setup">
      <div className="player-row">
        <div className="player-meta">
          <span className="player-label">Player {index + 1}</span>
          <span className={`player-color-chip ${color.toLowerCase()}`}>
            {color}
          </span>
        </div>
        <Select
          size="small"
          fullWidth
          value={player.key}
          onChange={(event) => onPlayerChange(event.target.value as PlayerKey)}
        >
          {available.map((option) => (
            <MenuItem
              key={option.key}
              value={option.key}
              disabled={
                isHuman(option.key) && humanCount >= 1 && !isHuman(player.key)
              }
            >
              {option.name}
            </MenuItem>
          ))}
        </Select>
        <Button
          variant="text"
          className="remove-player-btn"
          disabled={!canRemove}
          onClick={onRemove}
        >
          Remove
        </Button>
      </div>
      {selected?.is_bot && selected.params.length > 0 && (
        <div className="player-params">
          {selected.params.map((param) =>
            param.type === "bool" ? (
              <label
                className="player-param player-param-checkbox"
                key={param.name}
              >
                <Checkbox
                  checked={Boolean(paramValue(param))}
                  onChange={(event) =>
                    onParamChange(param.name, event.target.checked)
                  }
                />
                {param.name.replaceAll("_", " ")}
              </label>
            ) : param.choices ? (
              <Select
                className="player-param"
                key={param.name}
                size="small"
                aria-label={param.name.replaceAll("_", " ")}
                value={paramValue(param) ?? ""}
                onChange={(event) =>
                  onParamChange(
                    param.name,
                    parseValue(param, String(event.target.value)),
                  )
                }
              >
                {param.choices.map((choice) => (
                  <MenuItem key={choice} value={choice}>
                    {String(choice)}
                  </MenuItem>
                ))}
              </Select>
            ) : (
              <TextField
                className="player-param"
                key={param.name}
                size="small"
                label={param.name.replaceAll("_", " ")}
                type={param.type === "str" ? "text" : "number"}
                value={paramValue(param) ?? ""}
                onChange={(event) =>
                  onParamChange(
                    param.name,
                    parseValue(param, event.target.value),
                  )
                }
              />
            ),
          )}
        </div>
      )}
    </div>
  );
}
