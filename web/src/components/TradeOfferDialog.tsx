import { useEffect, useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
} from "@mui/material";

import type { ResourceCard } from "../utils/api.types";
import { RESOURCE_ORDER } from "../utils/resources";
import {
  emptyCounts,
  offerIsValid,
  type ResourceCounts,
} from "../utils/trade";

function CounterRow({
  label,
  counts,
  limit,
  blocked,
  onChange,
}: {
  label: string;
  counts: ResourceCounts;
  limit?: ResourceCounts;
  blocked: ResourceCounts;
  onChange: (resource: ResourceCard, next: number) => void;
}) {
  return (
    <div>
      <p>{label}</p>
      {RESOURCE_ORDER.map((resource) => {
        const count = counts[resource];
        const cap = limit?.[resource] ?? 4;
        return (
          <div key={resource}>
            <span>{resource}</span>
            <Button
              disabled={count === 0}
              onClick={() => onChange(resource, count - 1)}
            >
              −
            </Button>
            <span>{count}</span>
            <Button
              disabled={count >= cap || blocked[resource] > 0}
              onClick={() => onChange(resource, count + 1)}
            >
              +
            </Button>
          </div>
        );
      })}
    </div>
  );
}

export default function TradeOfferDialog({
  open,
  hand,
  onClose,
  onOffer,
}: {
  open: boolean;
  hand: ResourceCounts;
  onClose: () => void;
  onOffer: (giving: ResourceCounts, receiving: ResourceCounts) => void;
}) {
  const [giving, setGiving] = useState(emptyCounts);
  const [receiving, setReceiving] = useState(emptyCounts);

  useEffect(() => {
    if (open) {
      setGiving(emptyCounts());
      setReceiving(emptyCounts());
    }
  }, [open]);

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Offer a trade</DialogTitle>
      <DialogContent>
        <CounterRow
          label="You give"
          counts={giving}
          limit={hand}
          blocked={receiving}
          onChange={(resource, next) =>
            setGiving({ ...giving, [resource]: next })
          }
        />
        <CounterRow
          label="You want"
          counts={receiving}
          blocked={giving}
          onChange={(resource, next) =>
            setReceiving({ ...receiving, [resource]: next })
          }
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          disabled={!offerIsValid(giving, receiving)}
          onClick={() => onOffer(giving, receiving)}
        >
          Offer
        </Button>
      </DialogActions>
    </Dialog>
  );
}
