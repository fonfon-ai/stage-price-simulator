/** rule_v0.1: backend/app/calculation/recommender.py の移植。 */
import * as c from "./constants";
import { simulate } from "./simulator";
import type { DemandFeatures, Recommendation, ScenarioResult } from "./types";
import type { VenueCandidate } from "../types";

function priceRange(priceMin: number, priceMax: number, step: number = c.PRICE_STEP): number[] {
  let lo = priceMin;
  let hi = priceMax;
  if (lo > hi) [lo, hi] = [hi, lo];
  const prices: number[] = [];
  for (let p = lo; p <= hi; p += step) prices.push(p);
  if (prices.length === 0 || prices[prices.length - 1] !== hi) prices.push(hi);
  return Array.from(new Set(prices)).sort((a, b) => a - b);
}

export function runFullSearch(
  features: DemandFeatures,
  venues: VenueCandidate[],
  numPerformancesCandidates: number[],
  priceMin: number,
  priceMax: number
): ScenarioResult[] {
  const prices = priceRange(priceMin, priceMax);
  const scenarios: ScenarioResult[] = [];
  for (const venue of venues) {
    for (const numPerformances of numPerformancesCandidates) {
      for (const price of prices) {
        scenarios.push(simulate(features, venue, price, numPerformances));
      }
    }
  }
  return scenarios;
}

function normalize(values: number[]): number[] {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  if (hi - lo < 1e-9) return values.map(() => 1.0);
  return values.map((v) => (v - lo) / (hi - lo));
}

function occupancyCloseness(occupancyRate: number): number {
  const [lo, hi] = c.BALANCE_TARGET_OCCUPANCY_RANGE;
  if (occupancyRate >= lo && occupancyRate <= hi) return 1.0;
  if (occupancyRate < lo) return Math.max(0.0, 1 - (lo - occupancyRate) / lo);
  return Math.max(0.0, 1 - (occupancyRate - hi) / (1 - hi));
}

export function recommend(scenarios: ScenarioResult[], baselinePrice: number): Recommendation {
  if (scenarios.length === 0) {
    throw new Error("At least one scenario is required to recommend a price.");
  }

  const selloutCandidates = scenarios.filter(
    (s) => s.occupancy_rate >= c.SELLOUT_TARGET_OCCUPANCY
  );
  const selloutScenario =
    selloutCandidates.length > 0
      ? selloutCandidates.reduce((a, b) => (b.price > a.price ? b : a))
      : scenarios.reduce((a, b) => (b.occupancy_rate > a.occupancy_rate ? b : a));

  const revenueScenario = scenarios.reduce((a, b) => (b.revenue > a.revenue ? b : a));
  const profitScenario = scenarios.reduce((a, b) => (b.profit > a.profit ? b : a));

  const occupancyClosenessArr = scenarios.map((s) => occupancyCloseness(s.occupancy_rate));
  const revenueNorm = normalize(scenarios.map((s) => s.revenue));
  const profitNorm = normalize(scenarios.map((s) => s.profit));
  const discountPenalty = scenarios.map((s) =>
    baselinePrice ? Math.max(0.0, (baselinePrice - s.price) / baselinePrice) : 0.0
  );

  const scores = scenarios.map(
    (_, i) =>
      c.BALANCE_WEIGHT_OCCUPANCY * occupancyClosenessArr[i] +
      c.BALANCE_WEIGHT_REVENUE * revenueNorm[i] +
      c.BALANCE_WEIGHT_PROFIT * profitNorm[i] -
      c.BALANCE_WEIGHT_DISCOUNT_PENALTY * discountPenalty[i]
  );
  let bestIdx = 0;
  for (let i = 1; i < scores.length; i++) if (scores[i] > scores[bestIdx]) bestIdx = i;
  const balanceScenario = scenarios[bestIdx];
  const maxScore = scores[bestIdx];

  const sameComboPrices = scenarios
    .filter(
      (s, i) =>
        s.venue_name === balanceScenario.venue_name &&
        s.num_performances === balanceScenario.num_performances &&
        scores[i] >= maxScore * c.RECOMMENDED_RANGE_SCORE_THRESHOLD
    )
    .map((s) => s.price);
  const recommendedPriceRange: [number, number] = [
    Math.min(...sameComboPrices),
    Math.max(...sameComboPrices),
  ];

  return {
    sellout_price: selloutScenario.price,
    revenue_price: revenueScenario.price,
    profit_price: profitScenario.price,
    balance_price: balanceScenario.price,
    recommended_price_range: recommendedPriceRange,
    sellout_scenario: selloutScenario,
    revenue_scenario: revenueScenario,
    profit_scenario: profitScenario,
    balance_scenario: balanceScenario,
    all_scenarios: scenarios,
  };
}
