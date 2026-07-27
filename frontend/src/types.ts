export type Genre = "play" | "conte" | "other";
export type RarityLevel = "low" | "mid" | "high";

export interface GroupInfo {
  name: string;
  genre: Genre;
  years_active: number;
  sns_x_followers: number;
  sns_instagram_followers: number;
  sns_youtube_subscribers: number;
  sns_other_followers: number;
}

export interface PastPerformance {
  name: string;
  performance_date: string;
  prefecture: string;
  area: string;
  venue_name: string;
  capacity: number;
  price: number;
  num_performances: number;
  tickets_sold: number;
  sold_out: boolean;
  days_before_sold_out: number | null;
  is_new_work: boolean;
  is_weekend_holiday: boolean;
  is_evening: boolean;
}

export interface CurrentProduction {
  area: string;
  performance_date: string | null;
  is_new_work: boolean;
  is_weekend_holiday: boolean;
  is_evening: boolean;
  rarity_level: RarityLevel;
  has_guest: boolean;
  is_special: boolean;
  price_min: number;
  price_max: number;
}

export interface VenueCandidate {
  name: string;
  area: string;
  capacity: number;
  venue_cost: number;
  walk_minutes: number;
  location_rating: number;
  brand_rating: number;
}

export interface SimulateRequest {
  group: GroupInfo;
  past_performances: PastPerformance[];
  current_production: CurrentProduction;
  venues: VenueCandidate[];
  num_performances_candidates: number[];
}

export interface ScenarioOut {
  venue_name: string;
  price: number;
  num_performances: number;
  available_seats: number;
  expected_demand: number;
  expected_sold: number;
  occupancy_rate: number;
  revenue: number;
  profit: number;
  venue_fit: "too_small" | "good" | "slightly_large" | "too_large";
  venue_fit_message: string;
}

export interface ExplanationItem {
  factor: string;
  multiplier: number;
  description: string;
}

export interface ActualResultInput {
  run_id: number;
  scenario_id?: number | null;
  actual_price: number;
  actual_venue_name: string;
  actual_capacity?: number | null;
  actual_num_performances: number;
  actual_tickets_sold: number;
  actual_sold_out: boolean;
  actual_days_before_sold_out?: number | null;
}

export interface SimulateResponse {
  run_id: number;
  model_version: string;
  base_attendance_power: number;
  baseline_price: number;
  recommended_price_range: [number, number];
  balance_price: number;
  sellout_price: number;
  revenue_price: number;
  profit_price: number;
  balance_scenario: ScenarioOut;
  sellout_scenario: ScenarioOut;
  revenue_scenario: ScenarioOut;
  profit_scenario: ScenarioOut;
  scenarios: ScenarioOut[];
  explanation: ExplanationItem[];
  disclaimer: string;
}
