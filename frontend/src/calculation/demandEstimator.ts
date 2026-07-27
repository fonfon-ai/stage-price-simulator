/**
 * 需要推定コンポーネント。rule_v0.1。
 * backend/app/calculation/demand_estimator.py (RuleBasedDemandEstimator) の移植。
 * ロジック・係数は一切変更しないこと。
 */
import * as c from "./constants";
import type { DemandEstimate, DemandFeatures, ExplanationItem } from "./types";
import type { PastPerformance } from "../types";

function correctedAttendance(perf: PastPerformance): number {
  if (!perf.sold_out) return perf.tickets_sold;
  const days = perf.days_before_sold_out ?? 0;
  const factor =
    c.SOLD_OUT_BASE_CORRECTION +
    Math.min(
      c.SOLD_OUT_CORRECTION_CAP - c.SOLD_OUT_BASE_CORRECTION,
      days * c.SOLD_OUT_EARLY_BONUS_PER_DAY
    );
  return perf.tickets_sold * factor;
}

function weights(n: number): number[] {
  const raw = Array.from({ length: n }, (_, i) => c.ATTENDANCE_DECAY ** i);
  const total = raw.reduce((a, b) => a + b, 0);
  return raw.map((w) => w / total);
}

function clip(value: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, value));
}

export function estimateDemand(features: DemandFeatures): DemandEstimate {
  const explanation: ExplanationItem[] = [];

  const pastSorted = [...features.past_performances].sort((a, b) =>
    a.performance_date < b.performance_date ? 1 : a.performance_date > b.performance_date ? -1 : 0
  );
  if (pastSorted.length === 0) {
    throw new Error("At least one past performance is required to estimate demand.");
  }

  const w = weights(pastSorted.length);
  const perPerfAttendance = pastSorted.map(
    (p) => correctedAttendance(p) / Math.max(1, p.num_performances)
  );
  const baseAttendancePower = w.reduce((sum, wi, i) => sum + wi * perPerfAttendance[i], 0);
  const baselinePrice = w.reduce((sum, wi, i) => sum + wi * pastSorted[i].price, 0);

  explanation.push({
    factor: "base_attendance_power",
    multiplier: 1.0,
    description: `過去${pastSorted.length}公演の加重平均動員(直近を重視): ${baseAttendancePower.toFixed(0)}人/公演`,
  });

  let demand = baseAttendancePower;

  const relativeChange = baselinePrice ? (features.price - baselinePrice) / baselinePrice : 0.0;
  const priceFactor = clip(
    Math.exp(-c.PRICE_ELASTICITY * relativeChange),
    c.PRICE_FACTOR_MIN,
    c.PRICE_FACTOR_MAX
  );
  demand *= priceFactor;
  const pct = relativeChange * 100;
  explanation.push({
    factor: "price",
    multiplier: priceFactor,
    description: `過去平均価格(${baselinePrice.toFixed(0)}円)に対し価格を${pct >= 0 ? "+" : ""}${pct.toFixed(0)}%設定 → 需要${(priceFactor - 1) * 100 >= 0 ? "+" : ""}${((priceFactor - 1) * 100).toFixed(1)}%`,
  });

  const cp = features.current_production;

  if (cp.is_weekend_holiday) {
    demand *= c.WEEKEND_HOLIDAY_FACTOR;
    explanation.push({
      factor: "weekend_holiday",
      multiplier: c.WEEKEND_HOLIDAY_FACTOR,
      description: "土日祝のため需要+8%",
    });
  }
  if (cp.is_evening) {
    demand *= c.EVENING_FACTOR;
    explanation.push({ factor: "evening", multiplier: c.EVENING_FACTOR, description: "夜公演のため需要+5%" });
  }
  if (cp.is_new_work) {
    demand *= c.NEW_WORK_FACTOR;
    explanation.push({ factor: "new_work", multiplier: c.NEW_WORK_FACTOR, description: "新作のため需要+5%" });
  }

  const rarityFactor = c.RARITY_FACTOR[cp.rarity_level];
  if (rarityFactor !== 1.0) {
    demand *= rarityFactor;
    explanation.push({
      factor: "rarity",
      multiplier: rarityFactor,
      description: `希少性(${cp.rarity_level})により需要変動`,
    });
  }
  if (cp.has_guest) {
    demand *= c.GUEST_FACTOR;
    explanation.push({ factor: "guest", multiplier: c.GUEST_FACTOR, description: "ゲスト出演により需要+7%" });
  }
  if (cp.is_special) {
    demand *= c.SPECIAL_FACTOR;
    explanation.push({ factor: "special", multiplier: c.SPECIAL_FACTOR, description: "特別公演のため需要+10%" });
  }

  const venue = features.venue;
  const locationFactor = clip(
    c.LOCATION_BASE +
      c.LOCATION_RATING_STEP * (venue.location_rating - 3) -
      c.LOCATION_WALK_PENALTY_PER_MIN * venue.walk_minutes,
    c.LOCATION_FACTOR_MIN,
    c.LOCATION_FACTOR_MAX
  );
  demand *= locationFactor;
  explanation.push({
    factor: "location",
    multiplier: locationFactor,
    description: `立地評価${venue.location_rating}・徒歩${venue.walk_minutes}分による補正`,
  });

  const brandFactor = clip(
    c.BRAND_BASE + c.BRAND_RATING_STEP * (venue.brand_rating - 3),
    c.BRAND_FACTOR_MIN,
    c.BRAND_FACTOR_MAX
  );
  demand *= brandFactor;
  explanation.push({
    factor: "venue_brand",
    multiplier: brandFactor,
    description: `会場ブランド評価${venue.brand_rating}による補正`,
  });

  const weightedFollowers =
    features.group.sns_x_followers * c.SNS_WEIGHT_X +
    features.group.sns_instagram_followers * c.SNS_WEIGHT_INSTAGRAM +
    features.group.sns_youtube_subscribers * c.SNS_WEIGHT_YOUTUBE +
    features.group.sns_other_followers * c.SNS_WEIGHT_OTHER;
  const snsScore = Math.log1p(weightedFollowers);
  const snsFactor = 1 + Math.min(c.SNS_FACTOR_CAP, c.SNS_FACTOR_SCALE * snsScore);
  demand *= snsFactor;
  explanation.push({
    factor: "sns",
    multiplier: snsFactor,
    description: `SNS補助指標(補助情報、上限+${(c.SNS_FACTOR_CAP * 100).toFixed(0)}%): 需要${(snsFactor - 1) * 100 >= 0 ? "+" : ""}${((snsFactor - 1) * 100).toFixed(1)}%`,
  });

  const expectedDemandPerPerformance = demand;
  const totalExpectedDemand =
    expectedDemandPerPerformance * features.num_performances ** c.POOL_EXPONENT;
  if (features.num_performances > 1) {
    explanation.push({
      factor: "performance_count_pool",
      multiplier:
        features.num_performances ** c.POOL_EXPONENT / features.num_performances,
      description: `公演回数${features.num_performances}回のため観客プール逓減モデルを適用`,
    });
  }

  return {
    base_attendance_power: baseAttendancePower,
    baseline_price: baselinePrice,
    expected_demand_per_performance: expectedDemandPerPerformance,
    total_expected_demand: totalExpectedDemand,
    explanation,
  };
}
