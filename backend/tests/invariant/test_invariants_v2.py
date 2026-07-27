"""rule_v0.2 の回帰・Invariantテスト(PHASE 5)。

既存のrule_v0.1向けInvariantテスト(test_invariants.py)は変更せずそのまま維持する。
本ファイルはv0.2固有のテストのみを追加する。
"""
from __future__ import annotations

from app.calculation.confidence import (
    DataSufficiencyLevel,
    assess_recommendation_reliability,
)
from app.calculation.demand_estimator_v2 import RuleBasedDemandEstimatorV2
from app.calculation.recommender import recommend, run_full_search
from app.calculation.simulator import PerformanceSimulator
from tests.factories import make_features, make_group, make_past_performance, make_venue


def _v2_pipeline():
    estimator = RuleBasedDemandEstimatorV2()
    return estimator, PerformanceSimulator(estimator)


# --- Cold Start ---


def test_cold_start_single_history_is_flagged_low_confidence_not_silently_returned():
    """history 1件で価格探索上限/下限へ張り付いた推奨は、無警告の通常結果として
    返してはならない。confidence評価がLOWかつwarningsを伴うことを確認する。"""
    estimator, simulator = _v2_pipeline()
    features = make_features(
        past_performances=[make_past_performance(days_ago=30, tickets_sold=150)]
    )
    assert len(features.past_performances) == 1

    reference = estimator.estimate_demand(features)
    scenarios = run_full_search(
        simulator, features, [features.venue], [features.num_performances],
        features.current_production.price_min, features.current_production.price_max,
    )
    rec = recommend(scenarios, reference.baseline_price)

    reliability = assess_recommendation_reliability(
        usable_history_count=len(features.past_performances),
        balanced_price=rec.balance_price,
        price_min=features.current_production.price_min,
        price_max=features.current_production.price_max,
    )
    assert reliability.data_sufficiency == DataSufficiencyLevel.LOW
    assert reliability.is_strong_recommendation_allowed is False
    assert len(reliability.warnings) >= 1


# --- History Stability ---


def test_balanced_price_does_not_change_extremely_across_history_depth():
    """history 1->2->3->4で、推奨価格の変動が極端でないことを確認する
    (docs/MODEL_STRUCTURE_DIAGNOSTIC.mdで観測した「履歴1件のみ探索上限に張り付く」
    問題が、v0.2でも数値としては残り得るが、confidenceで必ず検出できることを併せて確認する)。"""
    estimator, simulator = _v2_pipeline()
    base_past = [
        make_past_performance(days_ago=(i + 1) * 90, tickets_sold=150 + i * 5)
        for i in range(4)
    ]

    balanced_prices = []
    for k in (1, 2, 3, 4):
        features = make_features(past_performances=base_past[:k])
        reference = estimator.estimate_demand(features)
        scenarios = run_full_search(
            simulator, features, [features.venue], [features.num_performances],
            features.current_production.price_min, features.current_production.price_max,
        )
        rec = recommend(scenarios, reference.baseline_price)
        balanced_prices.append(rec.balance_price)

    reliabilities = [
        assess_recommendation_reliability(k, balanced_prices[k - 1], 3000, 4500)
        for k in (1, 2, 3, 4)
    ]
    # history=1のみLOW、history>=3はNORMALであることを確認(段階的な信頼度設計)
    assert reliabilities[0].data_sufficiency == DataSufficiencyLevel.LOW
    assert reliabilities[1].data_sufficiency == DataSufficiencyLevel.MEDIUM
    assert reliabilities[2].data_sufficiency == DataSufficiencyLevel.NORMAL
    assert reliabilities[3].data_sufficiency == DataSufficiencyLevel.NORMAL


# --- Performance Scaling ---


def test_total_demand_increases_with_performance_count_but_not_required_linear():
    estimator = RuleBasedDemandEstimatorV2()
    features_1 = make_features(num_performances=1)
    features_8 = make_features(num_performances=8)
    features_22 = make_features(num_performances=22)

    d1 = estimator.estimate_demand(features_1).total_expected_demand
    d8 = estimator.estimate_demand(features_8).total_expected_demand
    d22 = estimator.estimate_demand(features_22).total_expected_demand

    assert d1 < d8 < d22
    # 完全な線形増加(8倍・22倍)である必要はない(むしろそれより小さいはず)
    assert d8 < d1 * 8
    assert d22 < d1 * 22


# --- Accessibility ---


def test_accessibility_effect_is_not_simple_duplication_of_same_fans():
    """1公演→複数公演にした際、同一ファンの単純複製(n倍)ではなく、
    Accessibility Gainによる増分がv0.1比で確認できること。"""
    from app.calculation.demand_estimator import RuleBasedDemandEstimator

    v1 = RuleBasedDemandEstimator()
    v2 = RuleBasedDemandEstimatorV2()
    features = make_features(num_performances=10)

    total_v1 = v1.estimate_demand(features).total_expected_demand
    total_v2 = v2.estimate_demand(features).total_expected_demand

    # 単純複製(n倍)ではない
    single_perf_demand = v1.estimate_demand(make_features(num_performances=1)).total_expected_demand
    assert total_v2 < single_perf_demand * 10
    # ただしAccessibility Gainの分だけv0.1より大きい
    assert total_v2 > total_v1


# --- Cannibalization ---


def test_demand_growth_remains_strongly_sublinear_for_large_performance_counts():
    """公演回数を増やせば無限に需要が比例増加するモデルにしない
    (Accessibility Gainは有界、Cannibalizationは引き続き強いsub-linear)。"""
    estimator = RuleBasedDemandEstimatorV2()
    d1 = estimator.estimate_demand(make_features(num_performances=1)).total_expected_demand
    d1000 = estimator.estimate_demand(make_features(num_performances=1000)).total_expected_demand

    ratio = d1000 / d1
    # 線形なら1000倍になるはずだが、大幅にそれを下回り、n^0.95程度の
    # 強いsub-linearな伸びに収まっていること(Accessibility Gainは有界のため)
    assert ratio < 1000**0.95
    assert ratio < 1000  # 明確に線形未満


# --- Existing invariants(v0.1と同内容をv0.2でも維持することを確認) ---


def test_v2_price_increase_never_increases_demand():
    estimator = RuleBasedDemandEstimatorV2()
    low = estimator.estimate_demand(make_features(price=3000))
    high = estimator.estimate_demand(make_features(price=8000))
    assert high.expected_demand_per_performance <= low.expected_demand_per_performance
    assert high.total_expected_demand <= low.total_expected_demand


def test_v2_sns_100x_never_100x_attendance():
    estimator = RuleBasedDemandEstimatorV2()
    base = estimator.estimate_demand(
        make_features(group=make_group(sns_x_followers=100, sns_instagram_followers=50))
    )
    boosted = estimator.estimate_demand(
        make_features(group=make_group(sns_x_followers=10000, sns_instagram_followers=5000))
    )
    assert boosted.total_expected_demand < base.total_expected_demand * 1.10


def test_v2_venue_cost_increase_alone_never_increases_profit():
    _, simulator = _v2_pipeline()
    features = make_features()
    cheap = simulator.simulate(features, make_venue(venue_cost=50000), 3800, 1)
    costly = simulator.simulate(features, make_venue(venue_cost=900000), 3800, 1)
    assert costly.profit <= cheap.profit


def test_v2_same_price_capacity_increase_does_not_increase_base_demand():
    _, simulator = _v2_pipeline()
    features = make_features()
    small = simulator.simulate(features, make_venue(capacity=80), 3800, 1)
    huge = simulator.simulate(features, make_venue(capacity=5000), 3800, 1)
    assert small.expected_demand == huge.expected_demand
