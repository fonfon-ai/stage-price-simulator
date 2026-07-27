"""極端値(Boundary)テスト。クラッシュしないこと、および異常な推奨値が出ないことを確認する。"""
from __future__ import annotations

import math

import pytest

from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.recommender import recommend, run_full_search
from app.calculation.simulator import PerformanceSimulator
from tests.factories import make_features, make_group, make_past_performance, make_venue


def _assert_finite_and_sane(estimate):
    assert math.isfinite(estimate.base_attendance_power)
    assert math.isfinite(estimate.expected_demand_per_performance)
    assert math.isfinite(estimate.total_expected_demand)
    assert estimate.base_attendance_power >= 0
    assert estimate.expected_demand_per_performance >= 0
    assert estimate.total_expected_demand >= 0


def test_zero_sns_followers_does_not_crash():
    estimator = RuleBasedDemandEstimator()
    estimate = estimator.estimate_demand(
        make_features(
            group=make_group(
                sns_x_followers=0,
                sns_instagram_followers=0,
                sns_youtube_subscribers=0,
                sns_other_followers=0,
            )
        )
    )
    _assert_finite_and_sane(estimate)


def test_zero_past_attendance_does_not_crash_and_yields_zero_demand():
    estimator = RuleBasedDemandEstimator()
    estimate = estimator.estimate_demand(
        make_features(
            past_performances=[make_past_performance(tickets_sold=0, sold_out=False)]
        )
    )
    _assert_finite_and_sane(estimate)
    assert estimate.base_attendance_power == 0


def test_capacity_of_one_does_not_crash():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features(venue=make_venue(capacity=1))
    scenario = simulator.simulate(features, features.venue, price=3500, num_performances=1)
    assert scenario.available_seats == 1
    assert 0 <= scenario.expected_sold <= 1


def test_capacity_of_5000_does_not_crash():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features(venue=make_venue(capacity=5000))
    scenario = simulator.simulate(features, features.venue, price=3500, num_performances=1)
    assert scenario.expected_sold <= scenario.available_seats
    # 巨大キャパでも需要そのものは過去実績相応に収まり、稼働率は極端に低くなるはず
    assert scenario.occupancy_rate < 0.2


@pytest.mark.parametrize("price", [500, 30000])
def test_extreme_ticket_prices_do_not_crash(price):
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    scenario = simulator.simulate(features, features.venue, price=price, num_performances=1)
    assert math.isfinite(scenario.revenue)
    assert math.isfinite(scenario.profit)
    assert scenario.expected_sold >= 0


def test_venue_cost_zero_does_not_crash():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    scenario = simulator.simulate(
        features, make_venue(venue_cost=0), price=3500, num_performances=1
    )
    assert scenario.profit == scenario.revenue


def test_venue_cost_far_exceeds_expected_revenue():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    scenario = simulator.simulate(
        features, make_venue(venue_cost=100_000_000), price=3500, num_performances=1
    )
    # 大赤字にはなるが、クラッシュせず有限値で返ってくることを確認
    assert math.isfinite(scenario.profit)
    assert scenario.profit < 0


def test_minimum_valid_input_single_past_performance():
    """過去公演が最低1件、他は最小限の入力でも一連の計算が完走する。"""
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)
    features = make_features(past_performances=[make_past_performance(tickets_sold=1, capacity=1)])
    estimate = estimator.estimate_demand(features)
    _assert_finite_and_sane(estimate)
    cp = features.current_production
    scenarios = run_full_search(
        simulator, features, [features.venue], [1], cp.price_min, cp.price_max
    )
    assert len(scenarios) > 0
    rec = recommend(scenarios, estimate.baseline_price)
    assert rec.balance_price > 0


def test_all_past_performances_sold_out():
    estimator = RuleBasedDemandEstimator()
    performances = [
        make_past_performance(
            days_ago=(i + 1) * 60, tickets_sold=150, sold_out=True, days_before_sold_out=3
        )
        for i in range(4)
    ]
    estimate = estimator.estimate_demand(make_features(past_performances=performances))
    _assert_finite_and_sane(estimate)
    # 完売のみのデータでは、補正により販売枚数(150)より基礎集客力が高く見積もられるはず
    assert estimate.base_attendance_power > 150


def test_all_past_performances_low_occupancy():
    estimator = RuleBasedDemandEstimator()
    performances = [
        make_past_performance(
            days_ago=(i + 1) * 60, tickets_sold=20, capacity=200, sold_out=False
        )
        for i in range(4)
    ]
    estimate = estimator.estimate_demand(make_features(past_performances=performances))
    _assert_finite_and_sane(estimate)
    assert estimate.base_attendance_power == pytest.approx(20, rel=0.01)


def test_full_pipeline_with_all_extremes_combined_does_not_crash():
    """followers=0, past attendance=1, capacity=1, price=30000, venue_cost=0 を同時に適用しても
    クラッシュしないこと。"""
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)
    features = make_features(
        group=make_group(
            sns_x_followers=0, sns_instagram_followers=0, sns_youtube_subscribers=0,
            sns_other_followers=0,
        ),
        past_performances=[
            make_past_performance(
                tickets_sold=1, capacity=1, sold_out=True, days_before_sold_out=0
            )
        ],
        venue=make_venue(capacity=1, venue_cost=0),
    )
    estimate = estimator.estimate_demand(features)
    _assert_finite_and_sane(estimate)
    scenario = simulator.simulate(features, features.venue, price=30000, num_performances=1)
    assert math.isfinite(scenario.revenue)
    assert math.isfinite(scenario.profit)
    assert scenario.expected_sold <= scenario.available_seats
