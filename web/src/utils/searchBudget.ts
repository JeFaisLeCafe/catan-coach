export type BudgetPreset =
  "immediate" | "1" | "5" | "30" | "120" | "custom" | "continuous";

export interface SearchBudgetChoice {
  preset: BudgetPreset;
  seconds: number;
}

export const ANALYSIS_PRESETS: BudgetPreset[] = [
  "immediate",
  "1",
  "5",
  "30",
  "120",
  "custom",
  "continuous",
];

export const BOT_PRESETS: BudgetPreset[] = ["immediate", "1", "5", "30"];

const ANALYSIS_KEY = "catan-coach.searchBudget";
const BOT_KEY = "catan-coach.botSearchBudget";
const DELAY_KEY = "catan-coach.presentationDelayMs";

export function budgetRequest(choice: SearchBudgetChoice): {
  mode: "immediate" | "timed" | "continuous";
  seconds?: number;
} {
  if (choice.preset === "continuous") {
    return { mode: "continuous" };
  }
  if (choice.preset === "immediate") {
    return { mode: "immediate" };
  }
  const seconds =
    choice.preset === "custom"
      ? choice.seconds
      : Number(choice.preset === "120" ? 120 : choice.preset);
  return { mode: "timed", seconds };
}

export function loadAnalysisBudget(): SearchBudgetChoice {
  return loadBudget(ANALYSIS_KEY, ANALYSIS_PRESETS, {
    preset: "immediate",
    seconds: 10,
  });
}

export function saveAnalysisBudget(choice: SearchBudgetChoice): void {
  saveBudget(ANALYSIS_KEY, choice);
}

export function loadBotBudget(): SearchBudgetChoice {
  return loadBudget(BOT_KEY, BOT_PRESETS, {
    preset: "immediate",
    seconds: 1,
  });
}

export function saveBotBudget(choice: SearchBudgetChoice): void {
  saveBudget(BOT_KEY, choice);
}

export function loadPresentationDelay(): number {
  const stored = Number(window.localStorage.getItem(DELAY_KEY));
  if (!Number.isFinite(stored)) {
    return 300;
  }
  return Math.min(5000, Math.max(0, stored));
}

export function savePresentationDelay(milliseconds: number): void {
  window.localStorage.setItem(DELAY_KEY, String(milliseconds));
}

function loadBudget(
  key: string,
  allowed: BudgetPreset[],
  fallback: SearchBudgetChoice,
): SearchBudgetChoice {
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(raw) as SearchBudgetChoice;
    if (!allowed.includes(parsed.preset) || !Number.isFinite(parsed.seconds)) {
      return fallback;
    }
    return {
      preset: parsed.preset,
      seconds: Math.min(600, Math.max(1, parsed.seconds)),
    };
  } catch {
    return fallback;
  }
}

function saveBudget(key: string, choice: SearchBudgetChoice): void {
  window.localStorage.setItem(key, JSON.stringify(choice));
}
