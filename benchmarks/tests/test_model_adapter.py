import datetime as dt
from typing import Any

from benchmarks.schema.models import AttendanceType, BenchmarkPerformance, OrganizationType, SoldOutStatus
from benchmarks.scripts.model_adapter import build_past_performances, build_target_features


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


def test_sold_out_history_without_observed_attendance_uses_capacity_as_lower_bound():
    """完売だが実売数が不明な履歴は、venue_capacity×performance_count(run全体の延べ席数)を
    『真の需要の下限』として扱い、sold_out=Trueフラグを立てる
    (=既存のcensored data補正がそのまま効く)。販売枚数=真の需要そのものとして固定してはいけない。

    performance_count=1の場合はvenue_capacityとvenue_capacity×performance_countが
    数値上一致するため、この単体テストだけでは掛け算の有無を検証できない
    (test_sold_out_total_lower_bound_multiplies_by_performance_count参照)。"""
    history = [
        _perf(
            benchmark_id="H-1",
            sold_out_status=SoldOutStatus.ALL_SOLD_OUT,
            observed_attendance=None,
            venue_capacity=150,
        )
    ]
    result = build_past_performances(history)
    assert len(result.past_performances) == 1
    pp = result.past_performances[0]
    assert pp.tickets_sold == 150
    assert pp.sold_out is True  # 既存のRuleBasedDemandEstimatorのcensored補正へ委ねる


def test_sold_out_total_lower_bound_multiplies_by_performance_count():
    """DEMAND_SEMANTICS_AUDIT.md で指摘された単位バグの回帰テスト。

    venue_capacity=386, performance_count=14, sold_out=true の場合、
    tickets_sold(run全体合計の下限) は 386×14=5,404 でなければならない。
    386(1公演あたりのcapacity)をそのままrun全体の値として使ってはいけない。
    """
    history = [
        _perf(
            benchmark_id="REAL-0002-like",
            sold_out_status=SoldOutStatus.ALL_SOLD_OUT,
            observed_attendance=None,
            venue_capacity=386,
            performance_count=14,
        )
    ]
    result = build_past_performances(history)
    assert len(result.past_performances) == 1
    pp = result.past_performances[0]
    assert pp.tickets_sold == 386 * 14
    assert pp.tickets_sold == 5404
    assert pp.tickets_sold != 386
    assert pp.sold_out is True


def test_history_without_any_derivable_attendance_is_excluded_not_fabricated():
    """完売でもなく実売数も不明な履歴は、値を捏造せず除外する。"""
    history = [
        _perf(
            benchmark_id="H-2",
            sold_out_status=SoldOutStatus.UNKNOWN,
            observed_attendance=None,
            venue_capacity=150,
        )
    ]
    result = build_past_performances(history)
    assert result.past_performances == []
    assert result.excluded_history_ids == ["H-2"]


def test_history_without_performance_count_is_excluded_not_fabricated():
    """公演回数が不明な履歴は、値を捏造せず除外する(実データでしばしば発生する)。"""
    history = [
        _perf(benchmark_id="H-NOCOUNT", observed_attendance=140, performance_count=None)
    ]
    result = build_past_performances(history)
    assert result.past_performances == []
    assert result.excluded_history_ids == ["H-NOCOUNT"]


def test_sold_out_history_with_missing_performance_count_does_not_use_capacity_alone():
    """DEMAND_SEMANTICS_AUDIT.md 回帰テスト: venue_capacity=386, performance_count不明,
    sold_out=true の場合、386をtickets_soldとして推測使用してはいけない
    (performance_countが分からない以上、run全体合計を計算できないため)。"""
    history = [
        _perf(
            benchmark_id="REAL-0002-nocounts",
            sold_out_status=SoldOutStatus.ALL_SOLD_OUT,
            observed_attendance=None,
            venue_capacity=386,
            performance_count=None,
        )
    ]
    result = build_past_performances(history)
    assert result.past_performances == []
    assert result.excluded_history_ids == ["REAL-0002-nocounts"]


def test_target_missing_performance_count_is_skipped_not_defaulted():
    history = [_perf(benchmark_id="H-1", observed_attendance=100)]
    result = build_past_performances(history)
    target = _perf(benchmark_id="TARGET", venue_capacity=200, performance_count=None)
    conv = build_target_features(target, result.past_performances)
    assert conv.features is None
    assert conv.skip_reason == "missing_target_performance_count"


def test_current_venue_capacity_is_not_applied_to_past_performances():
    """対象公演(target)のvenue_capacityを、capacity不明な過去公演へ自動流用してはいけない。"""
    history = [
        _perf(
            benchmark_id="H-3",
            observed_attendance=120,
            venue_capacity=None,  # 過去公演のcapacityは不明
        )
    ]
    result = build_past_performances(history)
    pp = result.past_performances[0]
    # target側のcapacity(例: 999)が紛れ込んでいないことを確認。
    # (capacityはdemand_estimator側で未使用の値のため、tickets_soldをplaceholderとして使う)
    assert pp.capacity != 999
    assert pp.capacity == 120


def test_target_missing_venue_capacity_is_skipped_not_defaulted():
    history = [_perf(benchmark_id="H-4", observed_attendance=100)]
    result = build_past_performances(history)
    target = _perf(benchmark_id="TARGET", venue_capacity=None)
    conv = build_target_features(target, result.past_performances)
    assert conv.features is None
    assert conv.skip_reason == "missing_target_venue_capacity"


def test_missing_optional_features_are_recorded_as_defaulted_not_silently_dropped():
    history = [_perf(benchmark_id="H-5", observed_attendance=100)]
    result = build_past_performances(history)
    target = _perf(
        benchmark_id="TARGET",
        venue_capacity=200,
        venue_location_rating=None,
        venue_brand_rating=None,
        sns_x_followers=None,
    )
    conv = build_target_features(target, result.past_performances)
    assert conv.features is not None
    assert "venue_location_rating" in conv.defaulted_fields
    assert "venue_brand_rating" in conv.defaulted_fields
    assert "sns_x_followers" in conv.defaulted_fields


def test_no_history_means_skip_with_reason():
    target = _perf(benchmark_id="TARGET", venue_capacity=200)
    conv = build_target_features(target, [])
    assert conv.features is None
    assert conv.skip_reason == "no_usable_history"
