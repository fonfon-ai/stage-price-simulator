"""価格探索・複数目的推奨ロジック。単一の「適正価格」ではなく、目的別に評価する。"""
from __future__ import annotations

from dataclasses import dataclass

from app.calculation import constants as c
from app.calculation.simulator import PerformanceSimulator
from app.calculation.types import DemandFeatures, ScenarioResult, VenueCandidate


@dataclass
class Recommendation:
    sellout_price: int
    revenue_price: int
    profit_price: int
    balance_price: int
    recommended_price_range: tuple[int, int]
    sellout_scenario: ScenarioResult
    revenue_scenario: ScenarioResult
    profit_scenario: ScenarioResult
    balance_scenario: ScenarioResult
    all_scenarios: list[ScenarioResult]


def _price_range(price_min: int, price_max: int, step: int = c.PRICE_STEP) -> list[int]:
    if price_min > price_max:
        price_min, price_max = price_max, price_min
    prices = list(range(price_min, price_max + 1, step))
    if not prices or prices[-1] != price_max:
        prices.append(price_max)
    return sorted(set(prices))


def run_full_search(
    simulator: PerformanceSimulator,
    features: DemandFeatures,
    venues: list[VenueCandidate],
    num_performances_candidates: list[int],
    price_min: int,
    price_max: int,
) -> list[ScenarioResult]:
    prices = _price_range(price_min, price_max)
    scenarios: list[ScenarioResult] = []
    for venue in venues:
        for num_performances in num_performances_candidates:
            for price in prices:
                scenarios.append(
                    simulator.simulate(features, venue, price, num_performances)
                )
    return scenarios


def _normalize(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [1.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _occupancy_closeness(occupancy_rate: float) -> float:
    lo, hi = c.BALANCE_TARGET_OCCUPANCY_RANGE
    if lo <= occupancy_rate <= hi:
        return 1.0
    if occupancy_rate < lo:
        return max(0.0, 1 - (lo - occupancy_rate) / lo)
    return max(0.0, 1 - (occupancy_rate - hi) / (1 - hi))


def recommend(scenarios: list[ScenarioResult], baseline_price: float) -> Recommendation:
    if not scenarios:
        raise ValueError("At least one scenario is required to recommend a price.")

    # 満席重視: 目標稼働率以上の中で最も高い価格。無ければ稼働率最大。
    sellout_candidates = [
        s for s in scenarios if s.occupancy_rate >= c.SELLOUT_TARGET_OCCUPANCY
    ]
    if sellout_candidates:
        sellout_scenario = max(sellout_candidates, key=lambda s: s.price)
    else:
        sellout_scenario = max(scenarios, key=lambda s: s.occupancy_rate)

    revenue_scenario = max(scenarios, key=lambda s: s.revenue)
    profit_scenario = max(scenarios, key=lambda s: s.profit)

    occupancy_closeness = [_occupancy_closeness(s.occupancy_rate) for s in scenarios]
    revenue_norm = _normalize([s.revenue for s in scenarios])
    profit_norm = _normalize([s.profit for s in scenarios])
    discount_penalty = [
        max(0.0, (baseline_price - s.price) / baseline_price) if baseline_price else 0.0
        for s in scenarios
    ]

    scores = [
        c.BALANCE_WEIGHT_OCCUPANCY * occ
        + c.BALANCE_WEIGHT_REVENUE * rev
        + c.BALANCE_WEIGHT_PROFIT * prof
        - c.BALANCE_WEIGHT_DISCOUNT_PENALTY * pen
        for occ, rev, prof, pen in zip(
            occupancy_closeness, revenue_norm, profit_norm, discount_penalty
        )
    ]
    best_idx = max(range(len(scenarios)), key=lambda i: scores[i])
    balance_scenario = scenarios[best_idx]
    max_score = scores[best_idx]

    same_combo_prices = [
        s.price
        for s, score in zip(scenarios, scores)
        if s.venue_name == balance_scenario.venue_name
        and s.num_performances == balance_scenario.num_performances
        and score >= max_score * c.RECOMMENDED_RANGE_SCORE_THRESHOLD
    ]
    recommended_price_range = (min(same_combo_prices), max(same_combo_prices))

    return Recommendation(
        sellout_price=sellout_scenario.price,
        revenue_price=revenue_scenario.price,
        profit_price=profit_scenario.price,
        balance_price=balance_scenario.price,
        recommended_price_range=recommended_price_range,
        sellout_scenario=sellout_scenario,
        revenue_scenario=revenue_scenario,
        profit_scenario=profit_scenario,
        balance_scenario=balance_scenario,
        all_scenarios=scenarios,
    )
