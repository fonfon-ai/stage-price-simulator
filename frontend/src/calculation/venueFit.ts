import * as c from "./constants";

export type VenueFitCategory = "too_small" | "good" | "slightly_large" | "too_large";

export function classifyVenueFit(occupancyRate: number): [VenueFitCategory, string] {
  if (occupancyRate >= c.VENUE_FIT_TOO_SMALL_THRESHOLD) {
    return [
      "too_small",
      `予想稼働率が${(occupancyRate * 100).toFixed(0)}%となり、現在の集客実績に対して` +
        "この会場は小さすぎる可能性があります。より大きな会場も検討できます。",
    ];
  }
  if (occupancyRate >= c.VENUE_FIT_GOOD_MIN) {
    return [
      "good",
      `予想稼働率は${(occupancyRate * 100).toFixed(0)}%で、現在の集客実績に対して適切な規模です。`,
    ];
  }
  if (occupancyRate >= c.VENUE_FIT_SLIGHTLY_LARGE_MIN) {
    return [
      "slightly_large",
      `予想稼働率は${(occupancyRate * 100).toFixed(0)}%となり、現在の集客実績に対して` +
        "やや大型です。空席リスクに注意してください。",
    ];
  }
  return [
    "too_large",
    `この会場では予想稼働率が${(occupancyRate * 100).toFixed(0)}%となり、` +
      "現在の集客実績に対して大きすぎる可能性があります。空席リスクが高い設計です。",
  ];
}
