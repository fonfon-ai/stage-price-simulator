import { describe, expect, it } from "vitest";
import { runFullSearch, recommend } from "./recommender";
import { estimateDemand } from "./demandEstimator";
import type { DemandFeatures } from "./types";
import type {
  CurrentProduction,
  GroupInfo,
  PastPerformance,
  VenueCandidate,
} from "../types";
import expected from "./__fixtures__/parity_expected.json";

// backend/_gen_parity_fixture.py が生成した同一入力・同一出力(rule_v0.1)。
// Python実装とTS移植の数値一致を検証する。

const group: GroupInfo = {
  name: "テスト劇団",
  genre: "play",
  years_active: 5,
  sns_x_followers: 12000,
  sns_instagram_followers: 8000,
  sns_youtube_subscribers: 3000,
  sns_other_followers: 500,
};

const pastPerformances: PastPerformance[] = [
  {
    name: "公演A",
    performance_date: "2025-03-01",
    prefecture: "東京都",
    area: "新宿",
    venue_name: "劇場A",
    capacity: 120,
    price: 3500,
    num_performances: 2,
    tickets_sold: 200,
    sold_out: true,
    days_before_sold_out: 5,
    is_new_work: true,
    is_weekend_holiday: true,
    is_evening: false,
  },
  {
    name: "公演B",
    performance_date: "2024-09-01",
    prefecture: "東京都",
    area: "下北沢",
    venue_name: "劇場B",
    capacity: 100,
    price: 3300,
    num_performances: 3,
    tickets_sold: 250,
    sold_out: false,
    days_before_sold_out: null,
    is_new_work: false,
    is_weekend_holiday: true,
    is_evening: true,
  },
  {
    name: "公演C",
    performance_date: "2024-03-01",
    prefecture: "東京都",
    area: "池袋",
    venue_name: "劇場C",
    capacity: 80,
    price: 3000,
    num_performances: 1,
    tickets_sold: 70,
    sold_out: false,
    days_before_sold_out: null,
    is_new_work: true,
    is_weekend_holiday: false,
    is_evening: false,
  },
];

const currentProduction: CurrentProduction = {
  area: "新宿",
  performance_date: "2026-03-01",
  is_new_work: true,
  is_weekend_holiday: true,
  is_evening: false,
  rarity_level: "mid",
  has_guest: true,
  is_special: false,
  price_min: 3000,
  price_max: 4200,
};

const venues: VenueCandidate[] = [
  {
    name: "会場X",
    area: "新宿",
    capacity: 150,
    venue_cost: 200000,
    walk_minutes: 5,
    location_rating: 4,
    brand_rating: 3,
  },
  {
    name: "会場Y",
    area: "渋谷",
    capacity: 250,
    venue_cost: 350000,
    walk_minutes: 10,
    location_rating: 3,
    brand_rating: 4,
  },
];

const numPerformancesCandidates = [1, 2, 3];

describe("rule_v0.1 TS port parity with Python implementation", () => {
  const baseFeatures: DemandFeatures = {
    group,
    past_performances: pastPerformances,
    current_production: currentProduction,
    venue: venues[0],
    price: currentProduction.price_min,
    num_performances: numPerformancesCandidates[0],
  };
  const referenceEstimate = estimateDemand(baseFeatures);
  const scenarios = runFullSearch(
    baseFeatures,
    venues,
    numPerformancesCandidates,
    currentProduction.price_min,
    currentProduction.price_max
  );
  const recommendation = recommend(scenarios, referenceEstimate.baseline_price);

  it("matches base_attendance_power and baseline_price", () => {
    expect(referenceEstimate.base_attendance_power).toBeCloseTo(
      expected.base_attendance_power,
      6
    );
    expect(referenceEstimate.baseline_price).toBeCloseTo(expected.baseline_price, 6);
  });

  it("matches recommended prices", () => {
    expect(recommendation.recommended_price_range).toEqual(
      expected.recommended_price_range
    );
    expect(recommendation.balance_price).toBe(expected.balance_price);
    expect(recommendation.sellout_price).toBe(expected.sellout_price);
    expect(recommendation.revenue_price).toBe(expected.revenue_price);
    expect(recommendation.profit_price).toBe(expected.profit_price);
  });

  it("matches every scenario numerically", () => {
    expect(scenarios.length).toBe(expected.scenarios.length);
    scenarios.forEach((s, i) => {
      const e = expected.scenarios[i];
      expect(s.venue_name).toBe(e.venue_name);
      expect(s.price).toBe(e.price);
      expect(s.num_performances).toBe(e.num_performances);
      expect(s.available_seats).toBe(e.available_seats);
      expect(s.expected_demand).toBeCloseTo(e.expected_demand, 6);
      expect(s.expected_sold).toBeCloseTo(e.expected_sold, 6);
      expect(s.occupancy_rate).toBeCloseTo(e.occupancy_rate, 6);
      expect(s.revenue).toBeCloseTo(e.revenue, 3);
      expect(s.profit).toBeCloseTo(e.profit, 3);
      expect(s.venue_fit).toBe(e.venue_fit);
    });
  });

  it("matches explanation multipliers", () => {
    expect(referenceEstimate.explanation.length).toBe(expected.explanation.length);
    referenceEstimate.explanation.forEach((e, i) => {
      expect(e.factor).toBe(expected.explanation[i].factor);
      expect(e.multiplier).toBeCloseTo(expected.explanation[i].multiplier, 6);
    });
  });
});
