import type {
  CurrentProduction,
  ExplanationItem,
  GroupInfo,
  PastPerformance,
  ScenarioOut,
  VenueCandidate,
} from "../types";

export type { ExplanationItem };

export interface DemandFeatures {
  group: GroupInfo;
  past_performances: PastPerformance[];
  current_production: CurrentProduction;
  venue: VenueCandidate;
  price: number;
  num_performances: number;
}

export interface DemandEstimate {
  base_attendance_power: number;
  baseline_price: number;
  expected_demand_per_performance: number;
  total_expected_demand: number;
  explanation: ExplanationItem[];
}

export type ScenarioResult = ScenarioOut;

export interface Recommendation {
  sellout_price: number;
  revenue_price: number;
  profit_price: number;
  balance_price: number;
  recommended_price_range: [number, number];
  sellout_scenario: ScenarioResult;
  revenue_scenario: ScenarioResult;
  profit_scenario: ScenarioResult;
  balance_scenario: ScenarioResult;
  all_scenarios: ScenarioResult[];
}
