"""Recommendation Stability: 入力のわずかな変化で推奨価格が不連続にジャンプしないことを確認する。

100円刻みの価格探索を採用しているため、隣接ステップ(100円)への変化は許容するが、
それを大きく超える不連続なジャンプ(例: 4,200円 -> 6,000円)が起きないことを検証する。
"""
from __future__ import annotations

from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.recommender import recommend, run_full_search
from app.calculation.simulator import PerformanceSimulator
from tests.factories import make_features, make_group, make_past_performance, make_venue

# 価格ステップ(100円)の何倍までの変化なら「連続的」とみなすかの許容値
MAX_ALLOWED_JUMP_STEPS = 3  # 300円までの変動は許容


def _balance_price(features):
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)
    reference = estimator.estimate_demand(features)
    scenarios = run_full_search(
        simulator,
        features,
        [features.venue],
        [features.num_performances],
        features.current_production.price_min,
        features.current_production.price_max,
    )
    rec = recommend(scenarios, reference.baseline_price)
    return rec.balance_price


def test_small_ticket_sold_change_does_not_cause_large_price_jump():
    base = make_features(past_performances=[make_past_performance(tickets_sold=180)])
    tweaked = make_features(past_performances=[make_past_performance(tickets_sold=181)])
    p1, p2 = _balance_price(base), _balance_price(tweaked)
    assert abs(p1 - p2) <= MAX_ALLOWED_JUMP_STEPS * 100, (
        f"tickets_sold 180->181 の微小変化で価格が {p1} -> {p2} に大きくジャンプした"
    )


def test_small_follower_change_does_not_cause_large_price_jump():
    base = make_features(group=make_group(sns_x_followers=3000, sns_instagram_followers=1500))
    tweaked = make_features(group=make_group(sns_x_followers=3050, sns_instagram_followers=1520))
    p1, p2 = _balance_price(base), _balance_price(tweaked)
    assert abs(p1 - p2) <= MAX_ALLOWED_JUMP_STEPS * 100, (
        f"フォロワー数の微小変化で価格が {p1} -> {p2} に大きくジャンプした"
    )


def test_small_price_range_shift_does_not_cause_large_price_jump():
    base = make_features()
    base.current_production.price_min = 3000
    base.current_production.price_max = 4500
    tweaked = make_features()
    tweaked.current_production.price_min = 3000
    tweaked.current_production.price_max = 4600
    p1, p2 = _balance_price(base), _balance_price(tweaked)
    assert abs(p1 - p2) <= MAX_ALLOWED_JUMP_STEPS * 100, (
        f"価格上限の微小変化(4500->4600)で価格が {p1} -> {p2} に大きくジャンプした"
    )


def test_small_venue_capacity_change_does_not_cause_large_price_jump():
    base = make_features(venue=make_venue(capacity=200))
    tweaked = make_features(venue=make_venue(capacity=205))
    p1, p2 = _balance_price(base), _balance_price(tweaked)
    assert abs(p1 - p2) <= MAX_ALLOWED_JUMP_STEPS * 100, (
        f"キャパの微小変化(200->205)で価格が {p1} -> {p2} に大きくジャンプした"
    )


def test_price_recommendation_is_continuous_across_a_price_sweep():
    """基準価格を1円刻みで少しずつ動かした際、バランス価格が滑らかに追従することを確認する
    (入力側のわずかな変化に対して出力が不連続に跳ねる箇所がないか)。"""
    prices = []
    for tickets in range(150, 220, 2):
        features = make_features(past_performances=[make_past_performance(tickets_sold=tickets)])
        prices.append(_balance_price(features))

    for p1, p2 in zip(prices, prices[1:]):
        assert abs(p1 - p2) <= MAX_ALLOWED_JUMP_STEPS * 100, (
            f"tickets_sold を2ずつ動かした際に価格が {p1} -> {p2} に不連続ジャンプした: {prices}"
        )
