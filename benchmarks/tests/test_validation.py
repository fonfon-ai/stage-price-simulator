import datetime as dt
from typing import Any

from benchmarks.schema.models import AttendanceType, BenchmarkPerformance, OrganizationType, SoldOutStatus
from benchmarks.schema.validation import has_errors, validate_case


def _base_case(**overrides: Any) -> BenchmarkPerformance:
    defaults: dict[str, Any] = dict(
        benchmark_id="T-1",
        organization_name="団体",
        organization_type=OrganizationType.THEATRE,
        production_name="公演",
        run_start_date=dt.date(2024, 1, 1),
        run_end_date=dt.date(2024, 1, 5),
        prefecture="東京都",
        city="新宿区",
        venue_name="会場",
        performance_count=4,
        regular_ticket_price=3000,
        sold_out_status=SoldOutStatus.UNKNOWN,
        observed_attendance_type=AttendanceType.UNKNOWN,
        is_synthetic=True,
    )
    defaults.update(overrides)
    return BenchmarkPerformance(**defaults)


def test_negative_ticket_price_is_error():
    issues = validate_case(_base_case(regular_ticket_price=-100))
    assert has_errors(issues)


def test_zero_capacity_is_error():
    issues = validate_case(_base_case(venue_capacity=0))
    assert has_errors(issues)


def test_end_before_start_is_error():
    issues = validate_case(
        _base_case(run_start_date=dt.date(2024, 5, 1), run_end_date=dt.date(2024, 4, 1))
    )
    assert has_errors(issues)


def test_exact_attendance_exceeding_capacity_is_error():
    issues = validate_case(
        _base_case(
            venue_capacity=100,
            performance_count=1,
            observed_attendance=150,
            observed_attendance_type=AttendanceType.EXACT,
        )
    )
    assert has_errors(issues)


def test_reported_total_exceeding_capacity_is_not_hard_error():
    """reported_total(裏取りの弱い報告値)はexactほど厳密ではないため、
    capacity超過だけで即rejectしない(過剰rejectを避ける方針)。"""
    issues = validate_case(
        _base_case(
            venue_capacity=100,
            performance_count=1,
            observed_attendance=150,
            observed_attendance_type=AttendanceType.REPORTED_TOTAL,
        )
    )
    assert not has_errors(issues)


def test_malformed_url_is_error():
    issues = validate_case(_base_case(source_url="not-a-url"))
    assert has_errors(issues)


def test_valid_url_has_no_url_error():
    issues = validate_case(_base_case(source_url="https://example.com/page"))
    assert not any(i.field == "source_url" and i.severity == "error" for i in issues)


def test_future_leakage_published_after_retrieved_is_error():
    issues = validate_case(
        _base_case(
            source_published_date=dt.date(2024, 6, 1),
            retrieved_at=dt.date(2024, 1, 1),
        )
    )
    assert has_errors(issues)


def test_sold_out_without_capacity_is_warning_not_error():
    """歴史的事情等でcapacityが分からないことは起こりうるため、警告に留め過剰rejectしない。"""
    issues = validate_case(
        _base_case(sold_out_status=SoldOutStatus.ALL_SOLD_OUT, venue_capacity=None)
    )
    assert not has_errors(issues)
    assert any(i.field == "venue_capacity" and i.severity == "warning" for i in issues)


def test_fully_valid_synthetic_case_has_no_errors():
    issues = validate_case(_base_case())
    assert not has_errors(issues)
