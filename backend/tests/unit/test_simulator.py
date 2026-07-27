from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.simulator import PerformanceSimulator
from tests.factories import make_features, make_venue


def test_revenue_equals_price_times_expected_sold():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    scenario = simulator.simulate(features, features.venue, price=3800, num_performances=1)
    assert scenario.revenue == scenario.expected_sold * scenario.price


def test_profit_equals_revenue_minus_venue_cost():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    venue = make_venue(venue_cost=150000)
    scenario = simulator.simulate(features, venue, price=3800, num_performances=2)
    assert scenario.profit == scenario.revenue - venue.venue_cost * 2


def test_expected_sold_never_exceeds_available_seats():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    # 小さいキャパで需要過多を発生させる
    features = make_features(venue=make_venue(capacity=10))
    scenario = simulator.simulate(features, features.venue, price=1000, num_performances=1)
    assert scenario.expected_sold <= scenario.available_seats


def test_venue_cost_increase_alone_does_not_increase_profit():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    cheap_venue = make_venue(venue_cost=100000)
    expensive_venue = make_venue(venue_cost=500000)
    cheap = simulator.simulate(features, cheap_venue, price=3800, num_performances=1)
    expensive = simulator.simulate(features, expensive_venue, price=3800, num_performances=1)
    assert expensive.profit < cheap.profit


def test_same_price_larger_capacity_does_not_increase_base_demand():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    small_venue = make_venue(capacity=100, location_rating=3, brand_rating=3, walk_minutes=5)
    large_venue = make_venue(capacity=1000, location_rating=3, brand_rating=3, walk_minutes=5)
    small = simulator.simulate(features, small_venue, price=3800, num_performances=1)
    large = simulator.simulate(features, large_venue, price=3800, num_performances=1)
    # capacity自体は需要(expected_demand)に影響しない。座席供給が変わるだけ。
    assert small.expected_demand == large.expected_demand
