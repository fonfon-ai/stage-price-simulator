import datetime as dt
from typing import Any

from benchmarks.schema.models import AttendanceType, BenchmarkPerformance, OrganizationType, SoldOutStatus
from benchmarks.scripts.backtest import BacktestPair
from benchmarks.scripts.cross_org_report import build_cross_organization_diagnostic_markdown
from benchmarks.scripts.metrics import evaluate_pair


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


def test_report_is_generated_with_single_organization_and_marks_data_insufficiency():
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        organization_name="診断用団体",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))

    markdown = build_cross_organization_diagnostic_markdown([result], "rule_v0.1")
    assert "rule_v0.1" in markdown
    assert "診断用団体" in markdown
    # 単一団体のみの場合、比較不能である旨が明示されること
    assert "のみです" in markdown


def test_report_handles_empty_results_without_crashing():
    markdown = build_cross_organization_diagnostic_markdown([], "rule_v0.1")
    assert "CROSS_ORGANIZATION_DIAGNOSTIC" in markdown
    assert "0団体" in markdown or "対象団体数(target登録済み)**: 0" in markdown


def test_report_does_not_hardcode_organization_names():
    """将来別団体のusable historyが増えても自動的に反映されるよう、
    集計ロジックが特定団体名をハードコードしていないことを、任意の団体名で確認する。"""
    history = [_perf(benchmark_id="H1", observed_attendance=150, venue_capacity=200)]
    target = _perf(
        benchmark_id="TARGET",
        organization_name="架空の新規団体XYZ",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        venue_capacity=200,
    )
    result = evaluate_pair(BacktestPair(target=target, history=history))
    markdown = build_cross_organization_diagnostic_markdown([result], "rule_v0.1")
    assert "架空の新規団体XYZ" in markdown
