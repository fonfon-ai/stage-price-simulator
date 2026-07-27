"""Calibration Test: 100件以上の代表シナリオが「意思決定として常識的か」を検証する。

予測精度(正解との誤差)ではなく、常識的な範囲に収まっているかを確認する。
"""
from __future__ import annotations

import pytest

from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.recommender import recommend, run_full_search
from app.calculation.simulator import PerformanceSimulator
from app.calculation.types import VenueFitCategory
from tests.calibration.dataset import generate_calibration_cases

CASES = generate_calibration_cases()


def test_dataset_has_at_least_100_cases():
    assert len(CASES) >= 100, f"calibration dataset must have >=100 cases, got {len(CASES)}"


def test_dataset_covers_all_required_tags():
    required_tags = {
        "attendance_30_50", "attendance_100", "attendance_200", "attendance_300_500",
        "past_performances_1", "past_performances_5plus",
        "rapid_growth", "declining_attendance",
        "sold_out", "sold_out_early", "not_sold_out",
        "sns_huge_only", "sns_low_strong_attendance",
        "weekday", "weekend_holiday",
        "new_work", "revival",
        "rarity_high", "frequent_performances",
        "venue_small", "venue_appropriate", "venue_too_large",
        "venue_cost_high", "venue_cost_low",
        "price_low", "price_normal", "price_high",
        "single_performance", "multiple_performances",
    }
    present = set()
    for c in CASES:
        present.update(c.tags)
    missing = required_tags - present
    assert not missing, f"calibration dataset is missing required tags: {missing}"


def _run_case(case):
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)
    # DemandFeaturesの構築に必要なvenueは1件目を代表として使う(基準価格算出用)
    from app.calculation.types import DemandFeatures

    base_features = DemandFeatures(
        group=case.group,
        past_performances=case.past_performances,
        current_production=case.current_production,
        venue=case.venues[0],
        price=case.current_production.price_min,
        num_performances=case.num_performances_candidates[0],
    )
    reference_estimate = estimator.estimate_demand(base_features)
    scenarios = run_full_search(
        simulator,
        base_features,
        case.venues,
        case.num_performances_candidates,
        case.current_production.price_min,
        case.current_production.price_max,
    )
    rec = recommend(scenarios, reference_estimate.baseline_price)
    return reference_estimate, scenarios, rec


@pytest.mark.parametrize("case", CASES, ids=[c.label for c in CASES])
def test_calibration_case_is_sane(case):
    estimate, scenarios, rec = _run_case(case)

    # --- 一般的なサニティチェック(全ケース共通) ---
    for s in scenarios:
        assert 0.0 <= s.occupancy_rate <= 1.0 + 1e-9, f"{case.label}: occupancy out of range"
        assert s.expected_sold <= s.available_seats + 1e-6, f"{case.label}: oversold"
        assert s.revenue >= 0, f"{case.label}: negative revenue"
    assert len(estimate.explanation) > 0, f"{case.label}: explanation must not be empty"
    lo, hi = rec.recommended_price_range
    assert case.current_production.price_min <= lo <= hi <= case.current_production.price_max

    # --- タグ別の常識チェック ---
    if "venue_too_large" in case.tags:
        target = next(s for s in scenarios if s.venue_name == case.venues[0].name)
        matching = [s for s in scenarios if s.venue_name == target.venue_name]
        best = max(matching, key=lambda s: s.occupancy_rate)
        assert best.venue_fit in (VenueFitCategory.SLIGHTLY_LARGE, VenueFitCategory.TOO_LARGE), (
            f"{case.label}: 明らかに大きすぎる会場なのにVenue Fitが'{best.venue_fit}'"
        )

    if "venue_small" in case.tags:
        target = next(s for s in scenarios if s.venue_name == case.venues[0].name)
        matching = [s for s in scenarios if s.venue_name == target.venue_name]
        best = min(matching, key=lambda s: abs(s.price - rec.balance_price))
        assert best.occupancy_rate >= 0.5, (
            f"{case.label}: 小会場なのに稼働率が{best.occupancy_rate:.2f}と低すぎる"
        )

    if "sns_huge_only" in case.tags:
        # SNSが巨大でも、過去の実動員規模を大きく超える会場では稼働率が高くなってはいけない
        huge_venue_scenarios = [s for s in scenarios if s.venue_name == "会場(大)"]
        if huge_venue_scenarios:
            best = max(huge_venue_scenarios, key=lambda s: s.occupancy_rate)
            assert best.occupancy_rate < 0.5, (
                f"{case.label}: SNSのみが巨大な団体で大会場の稼働率が"
                f"{best.occupancy_rate:.2f}と高すぎる(SNSに過大反応している疑いあり)"
            )
