import pytest

from app.calculation import constants as c1
from app.calculation import constants_v2 as c2
from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.demand_estimator_v2 import (
    RuleBasedDemandEstimatorV2,
    accessibility_gain,
    cannibalization_multiplier,
)
from tests.factories import make_features


def test_accessibility_gain_is_neutral_at_single_performance():
    assert accessibility_gain(1) == 1.0


def test_accessibility_gain_increases_with_performance_count():
    values = [accessibility_gain(n) for n in (1, 2, 5, 10, 22, 100)]
    for a, b in zip(values, values[1:]):
        assert b > a


def test_accessibility_gain_is_bounded():
    # nを非常に大きくしても上限(1+ACCESSIBILITY_GAIN_MAX)を超えない
    assert accessibility_gain(10_000_000) < 1 + c2.ACCESSIBILITY_GAIN_MAX + 1e-6


def test_cannibalization_multiplier_matches_v1_pool_exponent_formula():
    for n in (1, 2, 8, 16, 22):
        assert cannibalization_multiplier(n) == n**c1.POOL_EXPONENT


def test_v2_matches_v1_exactly_at_single_performance():
    """n=1ではAccessibility/Cannibalizationとも中立(倍率1.0)のため、
    v0.2はv0.1と完全に同一の結果を返す(アンカーポイントの保存)。"""
    estimator_v1 = RuleBasedDemandEstimator()
    estimator_v2 = RuleBasedDemandEstimatorV2()
    features = make_features(num_performances=1)

    e1 = estimator_v1.estimate_demand(features)
    e2 = estimator_v2.estimate_demand(features)

    assert e2.total_expected_demand == pytest.approx(e1.total_expected_demand)
    assert e2.base_attendance_power == e1.base_attendance_power
    assert e2.baseline_price == e1.baseline_price


def test_v2_total_demand_exceeds_v1_for_multiple_performances():
    """v0.2はAccessibility Gainの分だけ、複数公演時の総需要がv0.1より大きくなる。"""
    estimator_v1 = RuleBasedDemandEstimator()
    estimator_v2 = RuleBasedDemandEstimatorV2()
    features = make_features(num_performances=16)

    e1 = estimator_v1.estimate_demand(features)
    e2 = estimator_v2.estimate_demand(features)

    assert e2.total_expected_demand > e1.total_expected_demand


def test_v2_explanation_includes_new_factors_only_for_multiple_performances():
    estimator_v2 = RuleBasedDemandEstimatorV2()
    single = estimator_v2.estimate_demand(make_features(num_performances=1))
    multi = estimator_v2.estimate_demand(make_features(num_performances=5))

    single_factors = {e.factor for e in single.explanation}
    multi_factors = {e.factor for e in multi.explanation}
    assert "accessibility_gain_v2" not in single_factors
    assert "cannibalization_v2" not in single_factors
    assert "accessibility_gain_v2" in multi_factors
    assert "cannibalization_v2" in multi_factors


def test_v2_does_not_mutate_v1_constants():
    """v0.2の計算実行が、v0.1の凍結済み係数に一切影響しないことを確認する。"""
    original_pool_exponent = c1.POOL_EXPONENT
    estimator_v2 = RuleBasedDemandEstimatorV2()
    estimator_v2.estimate_demand(make_features(num_performances=10))
    assert c1.POOL_EXPONENT == original_pool_exponent
