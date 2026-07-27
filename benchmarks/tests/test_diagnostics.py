import datetime as dt

from benchmarks.schema.models import AttendanceType, BenchmarkPerformance, OrganizationType, SoldOutStatus
from benchmarks.scripts.backtest import BacktestPair
from benchmarks.scripts.diagnostics import (
    aggregate_by_history_depth,
    aggregate_by_organization,
    aggregate_by_performance_count,
    bucket_history_depth,
    bucket_performance_count,
)
from benchmarks.scripts.metrics import evaluate_pair


def _perf(**overrides) -> BenchmarkPerformance:
    defaults = dict(
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


def test_bucket_performance_count_boundaries():
    assert bucket_performance_count(1) == "1"
    assert bucket_performance_count(2) == "2-4"
    assert bucket_performance_count(4) == "2-4"
    assert bucket_performance_count(5) == "5-8"
    assert bucket_performance_count(8) == "5-8"
    assert bucket_performance_count(9) == "9-15"
    assert bucket_performance_count(15) == "9-15"
    assert bucket_performance_count(16) == "16-20"
    assert bucket_performance_count(20) == "16-20"
    assert bucket_performance_count(21) == "21+"
    assert bucket_performance_count(100) == "21+"
    assert bucket_performance_count(None) is None


def test_bucket_history_depth_boundaries():
    assert bucket_history_depth(1) == "1"
    assert bucket_history_depth(2) == "2"
    assert bucket_history_depth(3) == "3"
    assert bucket_history_depth(4) == "4+"
    assert bucket_history_depth(10) == "4+"


def test_aggregate_by_performance_count_marks_empty_buckets_without_evaluated_data():
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
        performance_count=3,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    stats = aggregate_by_performance_count([result])

    assert stats["2-4"].evaluated_count == 1
    assert stats["2-4"].has_evaluated_data is True
    # 他のbucketは対象0件、評価データなし(N/A相当)
    assert stats["1"].target_count == 0
    assert stats["1"].has_evaluated_data is False
    assert stats["21+"].target_count == 0


def test_aggregate_by_performance_count_includes_skipped_targets_for_bucketing():
    """skippedでもperformance_countが既知なら分類対象に含める(データ不足の可視化のため)。"""
    target = _perf(benchmark_id="TARGET", venue_capacity=None, performance_count=10)
    result = evaluate_pair(BacktestPair(target=target, history=[]))
    assert result.status == "skipped"
    stats = aggregate_by_performance_count([result])
    assert stats["9-15"].target_count == 1
    assert stats["9-15"].evaluated_count == 0
    assert stats["9-15"].has_evaluated_data is False


def test_aggregate_by_history_depth_only_counts_evaluated():
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    stats = aggregate_by_history_depth([result])
    assert stats["1"].evaluated_count == 1
    assert stats["2"].has_evaluated_data is False


def test_aggregate_by_organization_handles_multiple_orgs_with_missing_data():
    history_a = [_perf(benchmark_id="A-H1", observed_attendance=150, venue_capacity=200)]
    target_a = _perf(
        benchmark_id="A-TARGET",
        organization_name="団体A",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
    )
    result_a = evaluate_pair(BacktestPair(target=target_a, history=history_a))

    target_b = _perf(
        benchmark_id="B-TARGET",
        organization_name="団体B",
        venue_capacity=None,  # 評価不能
    )
    result_b = evaluate_pair(BacktestPair(target=target_b, history=[]))

    org_stats = aggregate_by_organization([result_a, result_b])
    assert org_stats["団体A"].evaluated_count == 1
    assert org_stats["団体A"].avg_price_gap is not None
    assert org_stats["団体B"].evaluated_count == 0
    assert org_stats["団体B"].avg_price_gap is None  # データ不足でN/A相当
