"""興行シミュレーション。DemandEstimatorの出力（需要）とキャパ・会場費から
売上・利益・稼働率を計算する。DemandEstimatorの具象実装には依存しない。
"""
from __future__ import annotations

from app.calculation.demand_estimator import DemandEstimator
from app.calculation.types import DemandFeatures, ScenarioResult, VenueCandidate
from app.calculation.venue_fit import classify_venue_fit


class PerformanceSimulator:
    def __init__(self, demand_estimator: DemandEstimator):
        self._demand_estimator = demand_estimator

    def simulate(
        self,
        features: DemandFeatures,
        venue: VenueCandidate,
        price: int,
        num_performances: int,
    ) -> ScenarioResult:
        scenario_features = DemandFeatures(
            group=features.group,
            past_performances=features.past_performances,
            current_production=features.current_production,
            venue=venue,
            price=price,
            num_performances=num_performances,
        )
        estimate = self._demand_estimator.estimate_demand(scenario_features)

        available_seats = venue.capacity * num_performances
        expected_sold = min(available_seats, estimate.total_expected_demand)
        occupancy_rate = expected_sold / available_seats if available_seats > 0 else 0.0
        revenue = expected_sold * price
        profit = revenue - venue.venue_cost * num_performances

        venue_fit, venue_fit_message = classify_venue_fit(occupancy_rate)

        return ScenarioResult(
            venue_name=venue.name,
            price=price,
            num_performances=num_performances,
            available_seats=available_seats,
            expected_demand=estimate.total_expected_demand,
            expected_sold=expected_sold,
            occupancy_rate=occupancy_rate,
            revenue=revenue,
            profit=profit,
            venue_fit=venue_fit,
            venue_fit_message=venue_fit_message,
        )
