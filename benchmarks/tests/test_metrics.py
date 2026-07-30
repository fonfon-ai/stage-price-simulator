import datetime as dt
from typing import Any

from benchmarks.schema.models import AttendanceType, BenchmarkPerformance, OrganizationType, SoldOutStatus
from benchmarks.scripts.backtest import BacktestPair
from benchmarks.scripts.metrics import _per_performance_demand, evaluate_pair
from benchmarks.scripts.model_adapter import build_past_performances, build_target_features

from benchmarks.scripts import _bootstrap  # noqa: F401
from app.calculation import constants as calc_constants  # noqa: E402
from app.calculation.demand_estimator import RuleBasedDemandEstimator  # noqa: E402


def _perf(**overrides: Any) -> BenchmarkPerformance:
    defaults: dict[str, Any] = dict(
        benchmark_id="T-1",
        organization_name="団体",
        organization_type=OrganizationType.THEATRE,
        production_name="公演",
        run_start_date=dt.date(2023, 1, 1),
        run_end_date=dt.date(2023, 1, 5),
        prefecture="東京都",
        city="新宿区",
        venue_name="会場",
        performance_count=1,
        regular_ticket_price=3000,
        sold_out_status=SoldOutStatus.UNKNOWN,
        observed_attendance_type=AttendanceType.UNKNOWN,
        is_synthetic=True,
    )
    defaults.update(overrides)
    return BenchmarkPerformance(**defaults)


def test_evaluated_result_stores_current_model_version():
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.status == "evaluated"
    assert result.model_version == "rule_v0.1"
    assert result.model_version == calc_constants.MODEL_VERSION


def test_sold_out_lower_bound_violation_true_when_prediction_below_available_seats():
    # 履歴の動員が極端に少ないため、predicted_demandはavailable_seatsを大きく下回るはず
    history = [
        _perf(benchmark_id="H1", observed_attendance=10, venue_capacity=500, performance_count=1)
    ]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=500,
        performance_count=1,
        sold_out_status=SoldOutStatus.ALL_SOLD_OUT,
        observed_attendance=None,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.status == "evaluated"
    assert result.sold_out_lower_bound_violation is True


def test_sold_out_lower_bound_violation_is_none_when_not_sold_out():
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
        sold_out_status=SoldOutStatus.NOT_SOLD_OUT,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.sold_out_lower_bound_violation is None


def test_price_gap_is_balanced_minus_actual_not_a_correctness_score():
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
        regular_ticket_price=3300,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.price_gap == result.balanced_price - 3300
    assert result.percentage_price_gap == (result.price_gap / 3300) * 100


def test_no_history_is_skipped_with_reason():
    target = _perf(benchmark_id="TARGET", venue_capacity=200)
    result = evaluate_pair(BacktestPair(target=target, history=[]))
    assert result.status == "skipped"
    assert result.skip_reason == "no_usable_history"


def test_recommended_capacity_is_same_unit_as_actual_venue_capacity():
    """DEMAND_SEMANTICS_AUDIT.md 回帰テスト: recommended_capacity_low/highは
    1公演あたり単位(actual_venue_capacityと同一単位)でなければならない。

    興行全体(run全体)単位のまま比較していた場合、num_performancesが大きいシナリオでは
    recommended_capacityがactual_venue_capacityよりも桁違いに大きくなってしまう。
    """
    history = [
        _perf(benchmark_id="H1", observed_attendance=800, venue_capacity=100, performance_count=8)
    ]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 10),
        venue_capacity=100,
        performance_count=10,
        regular_ticket_price=3000,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.status == "evaluated"
    # 興行全体(全10公演合計)の延べ席数は1,000。1公演あたり単位であれば
    # recommended_capacityはこれよりずっと小さいオーダー(venue_capacity=100前後)になるはず。
    run_level_total_seats = target.venue_capacity * target.performance_count
    assert result.recommended_capacity_low < run_level_total_seats
    assert result.recommended_capacity_high < run_level_total_seats


def test_recommended_capacity_matches_production_estimate_at_num_performances_one():
    """metrics.pyのrecommended_capacity算出が、Production側のestimate_demand()を
    num_performances=1で呼び出した結果と一致すること(独自の変換式を作っていないことの確認)。"""
    history = [
        _perf(benchmark_id="H1", observed_attendance=800, venue_capacity=100, performance_count=8)
    ]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 10),
        venue_capacity=100,
        performance_count=10,
        regular_ticket_price=3000,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))

    history_conv = build_past_performances(history)
    target_conv = build_target_features(target, history_conv.past_performances)
    assert target_conv.features is not None
    estimator = RuleBasedDemandEstimator()
    per_performance_demand = _per_performance_demand(
        estimator, target_conv.features, result.balanced_price
    )
    assert result.recommended_capacity_low == round(per_performance_demand / 1.0)
    assert result.recommended_capacity_high == round(
        per_performance_demand / calc_constants.VENUE_FIT_GOOD_MIN
    )


def test_performance_count_is_stored_on_result():
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
        performance_count=14,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.performance_count == 14


def test_performance_count_is_stored_even_when_skipped():
    target = _perf(benchmark_id="TARGET", venue_capacity=None, performance_count=21)
    result = evaluate_pair(BacktestPair(target=target, history=[]))
    assert result.status == "skipped"
    assert result.performance_count == 21


def test_demand_coverage_ratio_matches_predicted_demand_over_available_seats():
    """demand_coverage_ratio = predicted_total_demand / sold_out_lower_bound(=available_seats)。
    ユーザー提示の例(予測4,000 / 完売下限8,000 -> 0.50)と同じ定義であることを確認する。"""
    history = [
        _perf(
            benchmark_id="H1",
            sold_out_status=SoldOutStatus.ALL_SOLD_OUT,
            observed_attendance=None,
            venue_capacity=386,
            performance_count=14,
        )
    ]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2022, 1, 1),
        run_end_date=dt.date(2022, 1, 20),
        venue_capacity=386,
        performance_count=16,
        regular_ticket_price=8000,
        sold_out_status=SoldOutStatus.ALL_SOLD_OUT,
        observed_attendance=None,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.status == "evaluated"
    assert result.demand_coverage_ratio is not None
    available_seats = 386 * 16
    assert result.demand_coverage_ratio == (
        result.predicted_demand_at_actual_price / available_seats
    )
    # 完売なのに予測需要がキャパを下回っているケースなので1.0未満のはず
    assert result.demand_coverage_ratio < 1.0


def test_demand_coverage_ratio_is_none_when_not_sold_out():
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
        sold_out_status=SoldOutStatus.NOT_SOLD_OUT,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.demand_coverage_ratio is None


def test_price_search_boundary_hit_true_when_balanced_price_is_range_edge():
    """履歴1件のみの薄いケースでは、balanced_priceが探索レンジの端に張り付きやすい
    (docs/MODEL_STRUCTURE_DIAGNOSTIC.md参照)。"""
    history = [
        _perf(
            benchmark_id="H1",
            sold_out_status=SoldOutStatus.ALL_SOLD_OUT,
            observed_attendance=None,
            venue_capacity=386,
            performance_count=14,
            regular_ticket_price=5000,
        )
    ]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2022, 1, 1),
        run_end_date=dt.date(2022, 1, 20),
        venue_capacity=386,
        performance_count=16,
        regular_ticket_price=8000,
        sold_out_status=SoldOutStatus.ALL_SOLD_OUT,
        observed_attendance=None,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.price_search_boundary_hit is True
    assert result.balanced_price in (result.recommended_price_low, result.balanced_price)


def test_price_search_boundary_hit_false_when_balanced_price_is_interior():
    history = [
        _perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200, regular_ticket_price=3000),
        _perf(
            benchmark_id="H2",
            observed_attendance=150,
            venue_capacity=200,
            regular_ticket_price=3000,
            run_start_date=dt.date(2022, 6, 1),
            run_end_date=dt.date(2022, 6, 5),
        ),
    ]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
        regular_ticket_price=3000,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    assert result.price_search_boundary_hit is False


def test_predicted_demand_per_performance_reuses_production_num_performances_one():
    """predicted_demand_per_performanceが、Production側estimate_demand()を
    num_performances=1で呼び出した値と一致すること(独自式を作っていないことの確認)。"""
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
        regular_ticket_price=3300,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))

    history_conv = build_past_performances(history)
    target_conv = build_target_features(target, history_conv.past_performances)
    assert target_conv.features is not None
    estimator = RuleBasedDemandEstimator()
    expected = _per_performance_demand(estimator, target_conv.features, 3300)
    assert result.predicted_demand_per_performance == expected
    assert result.demand_per_performance_to_capacity_ratio == expected / 200
