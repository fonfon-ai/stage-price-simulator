import datetime as dt

from benchmarks.schema.models import AttendanceType, BenchmarkPerformance, OrganizationType, SoldOutStatus
from benchmarks.scripts.backtest import build_backtest_pairs, split_standard_and_special_condition_cases


def _perf(benchmark_id, org, start, end) -> BenchmarkPerformance:
    return BenchmarkPerformance(
        benchmark_id=benchmark_id,
        organization_name=org,
        organization_type=OrganizationType.THEATRE,
        production_name=f"{org}-{benchmark_id}",
        run_start_date=start,
        run_end_date=end,
        prefecture="東京都",
        city="新宿区",
        venue_name="会場",
        performance_count=1,
        regular_ticket_price=3000,
        sold_out_status=SoldOutStatus.UNKNOWN,
        observed_attendance_type=AttendanceType.UNKNOWN,
        is_synthetic=True,
    )


def test_earliest_performance_has_no_history():
    cases = [
        _perf("A2022", "団体X", dt.date(2022, 1, 1), dt.date(2022, 1, 5)),
        _perf("A2023", "団体X", dt.date(2023, 1, 1), dt.date(2023, 1, 5)),
        _perf("A2024", "団体X", dt.date(2024, 1, 1), dt.date(2024, 1, 5)),
    ]
    pairs = {p.target.benchmark_id: p for p in build_backtest_pairs(cases)}
    assert pairs["A2022"].history == []


def test_future_performances_never_appear_in_history():
    cases = [
        _perf("A2022", "団体X", dt.date(2022, 1, 1), dt.date(2022, 1, 5)),
        _perf("A2023", "団体X", dt.date(2023, 1, 1), dt.date(2023, 1, 5)),
        _perf("A2024", "団体X", dt.date(2024, 1, 1), dt.date(2024, 1, 5)),
        _perf("A2025", "団体X", dt.date(2025, 1, 1), dt.date(2025, 1, 5)),
    ]
    pairs = {p.target.benchmark_id: p for p in build_backtest_pairs(cases)}

    history_ids_for_2024 = {h.benchmark_id for h in pairs["A2024"].history}
    assert history_ids_for_2024 == {"A2022", "A2023"}
    assert "A2025" not in history_ids_for_2024


def test_different_organizations_do_not_share_history():
    cases = [
        _perf("X2022", "団体X", dt.date(2022, 1, 1), dt.date(2022, 1, 5)),
        _perf("Y2023", "団体Y", dt.date(2023, 1, 1), dt.date(2023, 1, 5)),
    ]
    pairs = {p.target.benchmark_id: p for p in build_backtest_pairs(cases)}
    assert pairs["Y2023"].history == []


def test_overlapping_run_is_not_treated_as_history():
    """run_end_dateがtargetのrun_start_date以降の場合(同時期公演)はhistoryに含めない。"""
    cases = [
        _perf("A", "団体X", dt.date(2024, 1, 1), dt.date(2024, 1, 10)),
        _perf("B", "団体X", dt.date(2024, 1, 5), dt.date(2024, 1, 15)),
    ]
    pairs = {p.target.benchmark_id: p for p in build_backtest_pairs(cases)}
    assert pairs["B"].history == []


def test_split_standard_and_special_condition_cases():
    standard = _perf("A", "団体X", dt.date(2024, 1, 1), dt.date(2024, 1, 5))
    special = _perf("B", "団体X", dt.date(2024, 2, 1), dt.date(2024, 2, 5))
    special.excluded_from_standard_backtest = True
    special.exclusion_reason = "covid_era_capacity_restriction"

    standard_cases, special_cases = split_standard_and_special_condition_cases([standard, special])
    assert [c.benchmark_id for c in standard_cases] == ["A"]
    assert [c.benchmark_id for c in special_cases] == ["B"]


def test_special_condition_case_does_not_leak_into_later_targets_history():
    """COVID等でexcluded_from_standard_backtest=trueの公演は、標準backtestの
    対象からも、後続公演のhistoryからも除外されなければならない(混入防止)。"""
    covid_case = _perf("COVID2020", "団体X", dt.date(2020, 1, 1), dt.date(2020, 1, 5))
    covid_case.excluded_from_standard_backtest = True
    covid_case.exclusion_reason = "covid_era_capacity_restriction"
    normal_case = _perf("A2021", "団体X", dt.date(2021, 1, 1), dt.date(2021, 1, 5))

    standard_cases, special_cases = split_standard_and_special_condition_cases(
        [covid_case, normal_case]
    )
    pairs = {p.target.benchmark_id: p for p in build_backtest_pairs(standard_cases)}

    assert "COVID2020" not in pairs  # 対象からも除外
    assert all(h.benchmark_id != "COVID2020" for h in pairs["A2021"].history)  # 履歴からも除外
