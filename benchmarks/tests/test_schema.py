import datetime as dt

from benchmarks.schema.models import (
    AttendanceType,
    BenchmarkPerformance,
    OrganizationType,
    SoldOutStatus,
)

MINIMAL_ROW = {
    "benchmark_id": "T-0001",
    "organization_name": "テスト団体",
    "organization_type": "theatre",
    "production_name": "テスト公演",
    "run_start_date": "2024-01-01",
    "run_end_date": "2024-01-05",
    "prefecture": "東京都",
    "city": "新宿区",
    "venue_name": "テスト会場",
    "performance_count": "4",
    "regular_ticket_price": "3000",
    "sold_out_status": "unknown",
    "observed_attendance_type": "unknown",
}


def test_unknown_optional_fields_become_none():
    case = BenchmarkPerformance.from_row(MINIMAL_ROW)
    assert case.venue_capacity is None
    assert case.observed_attendance is None
    assert case.sns_x_followers is None
    assert case.venue_location_rating is None
    assert case.source_url is None
    assert case.confidence is None
    assert case.is_synthetic is False


def test_sold_out_status_and_attendance_type_enums_are_distinct_categories():
    row = dict(MINIMAL_ROW)
    row["sold_out_status"] = "all_sold_out"
    row["observed_attendance_type"] = "lower_bound"
    case = BenchmarkPerformance.from_row(row)
    assert case.sold_out_status == SoldOutStatus.ALL_SOLD_OUT
    assert case.observed_attendance_type == AttendanceType.LOWER_BOUND
    assert case.organization_type == OrganizationType.THEATRE


def test_provenance_round_trip_through_csv_row():
    row = dict(MINIMAL_ROW)
    row.update(
        {
            "source_url": "https://example.com/press",
            "source_title": "公式発表",
            "source_publisher": "テスト団体",
            "source_published_date": "2024-01-10",
            "retrieved_at": "2024-01-11",
            "source_type": "official_organization",
            "confidence": "A",
        }
    )
    case = BenchmarkPerformance.from_row(row)
    assert case.source_url == "https://example.com/press"
    assert case.source_published_date == dt.date(2024, 1, 10)
    assert case.retrieved_at == dt.date(2024, 1, 11)
    assert case.confidence.value == "A"

    round_tripped = case.to_row()
    assert round_tripped["source_url"] == "https://example.com/press"
    assert round_tripped["confidence"] == "A"
    assert round_tripped["source_published_date"] == "2024-01-10"


def test_is_synthetic_flag_is_preserved():
    row = dict(MINIMAL_ROW)
    row["is_synthetic"] = "true"
    case = BenchmarkPerformance.from_row(row)
    assert case.is_synthetic is True
    assert case.to_row()["is_synthetic"] == "True"


def test_performance_count_is_optional_and_missing_becomes_none():
    """公開情報では公演回数が特定できないことがあるため、Optionalとして欠損を許容する。"""
    row = dict(MINIMAL_ROW)
    row["performance_count"] = ""
    case = BenchmarkPerformance.from_row(row)
    assert case.performance_count is None


def test_excluded_from_standard_backtest_flag_round_trips():
    row = dict(MINIMAL_ROW)
    row["excluded_from_standard_backtest"] = "true"
    row["exclusion_reason"] = "covid_era_capacity_restriction"
    case = BenchmarkPerformance.from_row(row)
    assert case.excluded_from_standard_backtest is True
    assert case.exclusion_reason == "covid_era_capacity_restriction"
    round_tripped = case.to_row()
    assert round_tripped["excluded_from_standard_backtest"] == "True"
    assert round_tripped["exclusion_reason"] == "covid_era_capacity_restriction"


def test_excluded_from_standard_backtest_defaults_to_false():
    case = BenchmarkPerformance.from_row(MINIMAL_ROW)
    assert case.excluded_from_standard_backtest is False
    assert case.exclusion_reason is None
