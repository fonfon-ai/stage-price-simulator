import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ResultDashboard from "./ResultDashboard";
import type { SimulateResponse } from "./types";

function makeScenario(overrides: Partial<SimulateResponse["balance_scenario"]> = {}) {
  return {
    venue_name: "会場A",
    price: 3800,
    num_performances: 1,
    available_seats: 200,
    expected_demand: 180,
    expected_sold: 180,
    occupancy_rate: 0.9,
    revenue: 684000,
    profit: 484000,
    venue_fit: "good" as const,
    venue_fit_message: "予想稼働率は90%で、適切な規模です。",
    ...overrides,
  };
}

function makeResult(): SimulateResponse {
  const scenario = makeScenario();
  return {
    run_id: 1,
    model_version: "rule_v0.1",
    base_attendance_power: 180,
    baseline_price: 3500,
    recommended_price_range: [3600, 4200],
    balance_price: 3800,
    sellout_price: 3600,
    revenue_price: 4200,
    profit_price: 4000,
    balance_scenario: scenario,
    sellout_scenario: scenario,
    revenue_scenario: scenario,
    profit_scenario: scenario,
    scenarios: [scenario],
    explanation: [{ factor: "base_attendance_power", multiplier: 1, description: "テスト説明" }],
    disclaimer: "本シミュレーションは過去実績と入力条件に基づく参考値です。",
  };
}

describe("ResultDashboard", () => {
  it("displays the disclaimer and price tiles", () => {
    render(<ResultDashboard result={makeResult()} />);
    expect(screen.getByText(/参考値です/)).toBeInTheDocument();
    expect(screen.getByText("バランス価格")).toBeInTheDocument();
    expect(screen.getAllByText("3,800円").length).toBeGreaterThan(0);
  });

  it("shows the explanation list", () => {
    render(<ResultDashboard result={makeResult()} />);
    expect(screen.getByText("テスト説明")).toBeInTheDocument();
  });
});
