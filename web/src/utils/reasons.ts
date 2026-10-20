import type { AnalysisReason } from "./api.types";

const REASON_COPY: Record<string, { name: string; meaning: string }> = {
  points: {
    name: "Victory points",
    meaning: "The score, including a hidden victory-point card",
  },
  hand: {
    name: "Cards in hand",
    meaning: "Resources and development cards being held",
  },
  production: {
    name: "Production",
    meaning: "The numbers and resources the buildings sit on",
  },
  "reachable expansion": {
    name: "Room to build",
    meaning: "Settlements, cities, and ports still in reach",
  },
  army: {
    name: "Army",
    meaning: "Knights and largest army",
  },
  road: {
    name: "Roads",
    meaning: "The road network and longest road",
  },
};

export function reasonName(label: string): string {
  return REASON_COPY[label]?.name ?? label;
}

export function reasonMeaning(label: string): string {
  return REASON_COPY[label]?.meaning ?? label;
}

export function reasonHint(reason: AnalysisReason): string {
  const meaning = reasonMeaning(reason.label);
  if (reason.delta > 0) {
    return `${meaning}. This raised the chance of winning.`;
  }
  if (reason.delta < 0) {
    return `${meaning}. This lowered the chance of winning.`;
  }
  return meaning;
}
