
import pytest

from app.calculation import constants as c
from app.calculation.demand_estimator import RuleBasedDemandEstimator, _corrected_attendance
from tests.factories import make_features, make_past_performance


def test_corrected_attendance_no_sold_out_returns_raw_tickets():
    perf = make_past_performance(sold_out=False, tickets_sold=150)
    assert _corrected_attendance(perf) == 150


def test_corrected_attendance_sold_out_applies_base_correction():
    perf = make_past_performance(sold_out=True, tickets_sold=200, days_before_sold_out=0)
    assert _corrected_attendance(perf) == pytest.approx(200 * c.SOLD_OUT_BASE_CORRECTION)


def test_corrected_attendance_early_sellout_is_capped():
    perf = make_past_performance(sold_out=True, tickets_sold=200, days_before_sold_out=100)
    assert _corrected_attendance(perf) == pytest.approx(200 * c.SOLD_OUT_CORRECTION_CAP)


def test_base_attendance_power_weights_recent_performances_more():
    estimator = RuleBasedDemandEstimator()
    # 直近が高動員、過去が低動員 → 加重平均は単純平均より高くなるはず
    features = make_features(
        past_performances=[
            make_past_performance(days_ago=10, tickets_sold=190, sold_out=False),
            make_past_performance(days_ago=100, tickets_sold=100, sold_out=False),
            make_past_performance(days_ago=200, tickets_sold=80, sold_out=False),
        ]
    )
    estimate = estimator.estimate_demand(features)
    simple_average = (190 + 100 + 80) / 3
    assert estimate.base_attendance_power > simple_average


def test_price_increase_never_increases_demand():
    estimator = RuleBasedDemandEstimator()
    base = make_features(price=3500)
    higher = make_features(price=5000)
    est_base = estimator.estimate_demand(base)
    est_higher = estimator.estimate_demand(higher)
    assert est_higher.expected_demand_per_performance <= est_base.expected_demand_per_performance


def test_price_factor_is_monotonically_non_increasing_in_price():
    estimator = RuleBasedDemandEstimator()
    prices = [2500, 3000, 3500, 4000, 4500, 5000, 6000]
    demands = [
        estimator.estimate_demand(make_features(price=p)).expected_demand_per_performance
        for p in prices
    ]
    for earlier, later in zip(demands, demands[1:]):
        assert later <= earlier + 1e-9


def test_sns_10x_does_not_10x_demand():
    estimator = RuleBasedDemandEstimator()
    from tests.factories import make_group

    low_sns = make_features(group=make_group(sns_x_followers=1000, sns_instagram_followers=500))
    high_sns = make_features(
        group=make_group(sns_x_followers=10000, sns_instagram_followers=5000)
    )
    d_low = estimator.estimate_demand(low_sns).expected_demand_per_performance
    d_high = estimator.estimate_demand(high_sns).expected_demand_per_performance
    assert d_high < d_low * 2  # 10倍のSNSでも需要は2倍未満に収まる（+5%キャップ）


def test_explanation_is_never_empty():
    estimator = RuleBasedDemandEstimator()
    estimate = estimator.estimate_demand(make_features())
    assert len(estimate.explanation) > 0


def test_requires_at_least_one_past_performance():
    estimator = RuleBasedDemandEstimator()
    with pytest.raises(ValueError):
        estimator.estimate_demand(make_features(past_performances=[]))
