import { Button, Dialog, DialogContent, DialogTitle } from "@mui/material";

import type { MoveRobberAction } from "../utils/api.types";

export default function RobberChoice({
  actions,
  onChoose,
  onClose,
}: {
  actions: MoveRobberAction[] | null;
  onChoose: (action: MoveRobberAction) => void;
  onClose: () => void;
}) {
  return (
    <Dialog open={actions !== null} onClose={onClose}>
      <DialogTitle>Who do you rob?</DialogTitle>
      <DialogContent>
        {actions?.map((action) => {
          const victim = action[2][1] ?? "Nobody";
          return (
            <Button key={victim} onClick={() => onChoose(action)}>
              {victim}
            </Button>
          );
        })}
      </DialogContent>
    </Dialog>
  );
}
