"""docs/TEST_PLAN.md の常識的制約(Invariant)を検証する。"""
from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.simulator import PerformanceSimulator
from tests.factories import (
    make_features,
    make_group,
    make_past_performance,
    make_venue,
)


def test_large_price_increase_never_increases_demand():
    estimator = RuleBasedDemandEstimator()
    low = estimator.estimate_demand(make_features(price=3000))
    high = estimator.estimate_demand(make_features(price=8000))
    assert high.expected_demand_per_performance <= low.expected_demand_per_performance


def test_expected_sold_never_exceeds_available_seats_across_many_prices():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features(venue=make_venue(capacity=50))
    for price in range(500, 10000, 500):
        scenario = simulator.simulate(features, features.venue, price, num_performances=3)
        assert scenario.expected_sold <= scenario.available_seats


def test_venue_cost_increase_alone_never_increases_profit():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    cheap = simulator.simulate(features, make_venue(venue_cost=50000), 3800, 1)
    costly = simulator.simulate(features, make_venue(venue_cost=900000), 3800, 1)
    assert costly.profit <= cheap.profit


def test_same_price_capacity_increase_does_not_increase_base_demand():
    simulator = PerformanceSimulator(RuleBasedDemandEstimator())
    features = make_features()
    small = simulator.simulate(features, make_venue(capacity=80), 3800, 1)
    huge = simulator.simulate(features, make_venue(capacity=5000), 3800, 1)
    assert small.expected_demand == huge.expected_demand


def test_sns_10x_never_10x_attendance():
    estimator = RuleBasedDemandEstimator()
    base = estimator.estimate_demand(
        make_features(group=make_group(sns_x_followers=500, sns_instagram_followers=300))
    )
    boosted = estimator.estimate_demand(
        make_features(group=make_group(sns_x_followers=5000, sns_instagram_followers=3000))
    )
    assert boosted.expected_demand_per_performance < base.expected_demand_per_performance * 10


def test_sns_100x_never_100x_attendance():
    """SNSフォロワーだけを100倍にしても、予想需要が100倍(あるいは大幅増)になってはいけない。"""
    estimator = RuleBasedDemandEstimator()
    base = estimator.estimate_demand(
        make_features(group=make_group(sns_x_followers=100, sns_instagram_followers=50))
    )
    boosted = estimator.estimate_demand(
        make_features(group=make_group(sns_x_followers=10000, sns_instagram_followers=5000))
    )
    # SNS補正は+5%キャップのため、100倍のフォロワーでも需要は1.05倍未満の増加に収まるはず
    assert boosted.expected_demand_per_performance < base.expected_demand_per_performance * 1.10


def test_sold_out_attendance_is_treated_as_lower_bound_not_true_demand():
    """完売公演の販売枚数は真の需要の上限ではなく下限として扱われるべき。

    全く同じ販売枚数でも、完売した公演はしていない公演より基礎集客力の推定値が
    高くなる(=販売枚数そのものを需要の天井として扱っていない)ことを確認する。
    """
    estimator = RuleBasedDemandEstimator()
    not_sold_out = estimator.estimate_demand(
        make_features(
            past_performances=[
                make_past_performance(days_ago=30, tickets_sold=200, sold_out=False)
            ]
        )
    )
    sold_out = estimator.estimate_demand(
        make_features(
            past_performances=[
                make_past_performance(
                    days_ago=30, tickets_sold=200, sold_out=True, days_before_sold_out=5
                )
            ]
        )
    )
    assert sold_out.base_attendance_power > not_sold_out.base_attendance_power


def test_doubling_performance_count_does_not_double_total_demand():
    """公演回数を2倍にしても総需要は単純に2倍にならない(観客プールの重複を考慮)。

    同一顧客が公演ごとに複製されるモデル(linear duplication)になっていないことの検証。
    """
    estimator = RuleBasedDemandEstimator()
    one_show = estimator.estimate_demand(make_features(num_performances=1))
    two_shows = estimator.estimate_demand(make_features(num_performances=2))
    four_shows = estimator.estimate_demand(make_features(num_performances=4))

    # 単純複製(linear duplication)なら total_expected_demand は num_performances に比例するはず。
    # 逓減モデルなら必ずそれより小さくなる。
    assert two_shows.total_expected_demand < 2 * one_show.total_expected_demand
    assert four_shows.total_expected_demand < 4 * one_show.total_expected_demand

    # 公演回数が増えるほど、1公演あたりの平均需要(カニバリゼーション)は減少するはず
    avg_demand_per_show_1 = one_show.total_expected_demand / 1
    avg_demand_per_show_2 = two_shows.total_expected_demand / 2
    avg_demand_per_show_4 = four_shows.total_expected_demand / 4
    assert avg_demand_per_show_2 < avg_demand_per_show_1
    assert avg_demand_per_show_4 < avg_demand_per_show_2


def test_performance_count_demand_growth_is_concave():
    """公演回数を増やすほど、追加1公演あたりの需要増分は逓減する(concave)。"""
    estimator = RuleBasedDemandEstimator()
    demands = [
        estimator.estimate_demand(make_features(num_performances=n)).total_expected_demand
        for n in range(1, 6)
    ]
    increments = [b - a for a, b in zip(demands, demands[1:])]
    for earlier, later in zip(increments, increments[1:]):
        assert later <= earlier + 1e-6, "公演回数を増やすほど追加需要が逓減していない"
