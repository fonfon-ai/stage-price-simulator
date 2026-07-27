/**
 * ローカル計算エンジンのエントリポイント。
 * backend/app/api/simulate.py の計算部分(DB永続化を除く)を
 * ブラウザ上でそのまま実行する rule_v0.1 の移植。
 */
import { MODEL_VERSION } from "./constants";
import { estimateDemand } from "./demandEstimator";
import { recommend, runFullSearch } from "./recommender";
import type { SimulateRequest, SimulateResponse } from "../types";

export const DISCLAIMER =
  "本シミュレーションは過去実績と入力条件に基づく参考値です。" +
  "実際の販売結果を保証するものではありません。";

let localRunCounter = 0;

export function runSimulationLocally(req: SimulateRequest): SimulateResponse {
  const baseFeatures = {
    group: req.group,
    past_performances: req.past_performances,
    current_production: req.current_production,
    venue: req.venues[0],
    price: req.current_production.price_min,
    num_performances: req.num_performances_candidates[0],
  };
  const referenceEstimate = estimateDemand(baseFeatures);

  const scenarios = runFullSearch(
    baseFeatures,
    req.venues,
    req.num_performances_candidates,
    req.current_production.price_min,
    req.current_production.price_max
  );
  const recommendation = recommend(scenarios, referenceEstimate.baseline_price);

  localRunCounter += 1;

  return {
    run_id: localRunCounter,
    model_version: MODEL_VERSION,
    base_attendance_power: referenceEstimate.base_attendance_power,
    baseline_price: referenceEstimate.baseline_price,
    recommended_price_range: recommendation.recommended_price_range,
    balance_price: recommendation.balance_price,
    sellout_price: recommendation.sellout_price,
    revenue_price: recommendation.revenue_price,
    profit_price: recommendation.profit_price,
    balance_scenario: recommendation.balance_scenario,
    sellout_scenario: recommendation.sellout_scenario,
    revenue_scenario: recommendation.revenue_scenario,
    profit_scenario: recommendation.profit_scenario,
    scenarios,
    explanation: referenceEstimate.explanation,
    disclaimer: DISCLAIMER,
  };
}
