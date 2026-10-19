import type { Color, OfferTradeAction, ResourceCard } from "./api.types";
import { RESOURCE_ORDER } from "./resources";

export type ResourceCounts = Record<ResourceCard, number>;

export function emptyCounts(): ResourceCounts {
  return { WOOD: 0, BRICK: 0, SHEEP: 0, WHEAT: 0, ORE: 0 };
}

export function offerIsValid(
  giving: ResourceCounts,
  receiving: ResourceCounts,
): boolean {
  const gives = RESOURCE_ORDER.some((resource) => giving[resource] > 0);
  const receives = RESOURCE_ORDER.some((resource) => receiving[resource] > 0);
  const overlaps = RESOURCE_ORDER.some(
    (resource) => giving[resource] > 0 && receiving[resource] > 0,
  );
  return gives && receives && !overlaps;
}

export function offerTradeAction(
  color: Color,
  giving: ResourceCounts,
  receiving: ResourceCounts,
): OfferTradeAction {
  return [
    color,
    "OFFER_TRADE",
    [
      ...RESOURCE_ORDER.map((resource) => giving[resource]),
      ...RESOURCE_ORDER.map((resource) => receiving[resource]),
    ],
  ];
}

export function describeFreqdeck(counts: number[]): string {
  const parts = RESOURCE_ORDER.flatMap((resource, index) => {
    const count = counts[index] ?? 0;
    return count > 0 ? [`${count} ${resource}`] : [];
  });
  return parts.join(", ");
}
