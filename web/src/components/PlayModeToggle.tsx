import Switch from "@mui/material/Switch";

import type { PlayMode } from "../utils/playMode";

export default function PlayModeToggle({
  mode,
  onChange,
}: {
  mode: PlayMode;
  onChange: (mode: PlayMode) => void;
}) {
  return (
    <div className="play-mode-toggle">
      <span>Challenge</span>
      <Switch
        checked={mode === "coach"}
        onChange={(_, checked) => onChange(checked ? "coach" : "challenge")}
        slotProps={{ input: { "aria-label": "Coach Mode" } }}
        color="primary"
      />
      <span>Coach</span>
    </div>
  );
}
