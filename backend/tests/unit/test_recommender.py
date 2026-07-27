from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.recommender import recommend, run_full_search
from app.calculation.simulator import PerformanceSimulator
from tests.factories import make_features, make_venue


def _search():
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)
    features = make_features()
    venues = [make_venue(name="A", capacity=200), make_venue(name="B", capacity=350)]
    scenarios = run_full_search(simulator, features, venues, [1, 2], 3000, 4500)
    return estimator, features, scenarios


def test_price_search_step_is_100_yen():
    _, _, scenarios = _search()
    prices = sorted({s.price for s in scenarios})
    assert prices[0] == 3000
    assert prices[-1] == 4500
    for a, b in zip(prices, prices[1:]):
        assert b - a == 100


def test_recommend_returns_all_four_objectives():
    estimator, features, scenarios = _search()
    baseline = estimator.estimate_demand(features).baseline_price
    rec = recommend(scenarios, baseline)
    assert rec.sellout_price > 0
    assert rec.revenue_price > 0
    assert rec.profit_price > 0
    assert rec.balance_price > 0


def test_recommended_price_range_is_within_search_bounds():
    estimator, features, scenarios = _search()
    baseline = estimator.estimate_demand(features).baseline_price
    rec = recommend(scenarios, baseline)
    lo, hi = rec.recommended_price_range
    assert 3000 <= lo <= hi <= 4500


def test_sellout_scenario_meets_target_occupancy_when_possible():
    estimator, features, scenarios = _search()
    baseline = estimator.estimate_demand(features).baseline_price
    rec = recommend(scenarios, baseline)
    at_or_above_target = [s for s in scenarios if s.occupancy_rate >= 0.90]
    if at_or_above_target:
        assert rec.sellout_scenario.occupancy_rate >= 0.90


def test_revenue_scenario_maximizes_price_times_sold():
    estimator, features, scenarios = _search()
    baseline = estimator.estimate_demand(features).baseline_price
    rec = recommend(scenarios, baseline)
    best_revenue = max(s.revenue for s in scenarios)
    assert rec.revenue_scenario.revenue == best_revenue


def test_profit_scenario_maximizes_profit():
    estimator, features, scenarios = _search()
    baseline = estimator.estimate_demand(features).baseline_price
    rec = recommend(scenarios, baseline)
    best_profit = max(s.profit for s in scenarios)
    assert rec.profit_scenario.profit == best_profit
