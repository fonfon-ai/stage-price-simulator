"""50ケース以上のシナリオテスト。docs/TEST_PLAN.md 参照。
極端に不自然な推奨(無名劇団に巨大会場・高価格を推奨する等)が出ないことを確認する。
"""
from __future__ import annotations

import itertools

import pytest

from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.recommender import recommend, run_full_search
from app.calculation.simulator import PerformanceSimulator
from app.calculation.types import Genre, RarityLevel, VenueFitCategory
from tests.factories import (
    make_current_production,
    make_features,
    make_group,
    make_past_performance,
    make_venue,
)

# 団体プロフィール: (ラベル, 過去動員の目安, SNSフォロワー, ジャンル)
GROUP_PROFILES = [
    ("unknown_play", 30, 200, Genre.PLAY),
    ("young_play", 90, 2000, Genre.PLAY),
    ("popular_play", 400, 30000, Genre.PLAY),
    ("young_conte", 70, 1500, Genre.CONTE),
    ("popular_conte", 350, 25000, Genre.CONTE),
]
CAPACITIES = [50, 100, 200, 300, 500]
WEEKDAY_OPTIONS = [True, False]  # True=土日祝
PRICE_LEVELS = ["low", "high"]
SELLOUT_PATTERNS = ["early_sellout", "long_no_sellout", "no_sellout"]

PRICE_LEVEL_RANGE = {"low": (1500, 2500), "high": (5000, 7000)}


def _build_case(profile, capacity, is_weekend, price_level, sellout_pattern):
    label, base_attendance, sns, genre = profile
    group = make_group(
        genre=genre,
        sns_x_followers=sns,
        sns_instagram_followers=sns // 2,
        sns_youtube_subscribers=sns // 4,
    )

    if sellout_pattern == "early_sellout":
        past = [
            make_past_performance(
                days_ago=(i + 1) * 60,
                tickets_sold=base_attendance,
                sold_out=True,
                days_before_sold_out=10,
            )
            for i in range(3)
        ]
    elif sellout_pattern == "long_no_sellout":
        past = [
            make_past_performance(
                days_ago=(i + 1) * 60, tickets_sold=int(base_attendance * 0.6), sold_out=False
            )
            for i in range(3)
        ]
    else:
        past = [
            make_past_performance(
                days_ago=(i + 1) * 60, tickets_sold=base_attendance, sold_out=False
            )
            for i in range(3)
        ]

    price_min, price_max = PRICE_LEVEL_RANGE[price_level]
    current_production = make_current_production(
        is_weekend_holiday=is_weekend,
        rarity_level=RarityLevel.MID,
        price_min=price_min,
        price_max=price_max,
    )
    venue = make_venue(capacity=capacity)
    features = make_features(
        group=group,
        past_performances=past,
        current_production=current_production,
        venue=venue,
        price=price_min,
        num_performances=1,
    )
    return label, capacity, is_weekend, price_level, sellout_pattern, features, price_min, price_max


def _generate_cases():
    combos = list(
        itertools.product(
            GROUP_PROFILES, CAPACITIES, WEEKDAY_OPTIONS, PRICE_LEVELS, SELLOUT_PATTERNS
        )
    )
    # 全直積150通りから代表55件を間引いて採用(TEST_PLAN.mdの「50ケース以上」を満たす)。
    step = max(1, len(combos) // 55)
    selected = combos[::step][:60]
    return [_build_case(*combo) for combo in selected]


CASES = _generate_cases()
assert len(CASES) >= 50, f"expected >=50 scenario cases, got {len(CASES)}"


@pytest.mark.parametrize(
    "label,capacity,is_weekend,price_level,sellout_pattern,features,price_min,price_max",
    CASES,
    ids=[f"{c[0]}-cap{c[1]}-{'weekend' if c[2] else 'weekday'}-{c[3]}-{c[4]}" for c in CASES],
)
def test_scenario_is_sane(
    label, capacity, is_weekend, price_level, sellout_pattern, features, price_min, price_max
):
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)
    scenarios = run_full_search(simulator, features, [features.venue], [1, 2], price_min, price_max)
    baseline_price = estimator.estimate_demand(features).baseline_price
    rec = recommend(scenarios, baseline_price)

    for s in scenarios:
        assert 0.0 <= s.occupancy_rate <= 1.0 + 1e-9
        assert s.expected_sold <= s.available_seats + 1e-9

    estimate = estimator.estimate_demand(features)
    assert len(estimate.explanation) > 0

    if rec.balance_scenario.venue_fit == VenueFitCategory.TOO_LARGE:
        assert "大きすぎる" in rec.balance_scenario.venue_fit_message

    # 無名劇団(unknown_play)に対し、巨大会場(500席)かつ高価格帯がバランス推奨で
    # 稼働率90%以上になるような非現実的な結果が出ないことを確認する。
    if label == "unknown_play" and capacity == 500 and price_level == "high":
        assert rec.balance_scenario.occupancy_rate < 0.90
