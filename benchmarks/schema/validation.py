"""Benchmark CSV入力のバリデーション。

方針: 明らかに物理的・時系列的に成立しない値は error、
判断が分かれうる/歴史的事情で成立しうるものは warning として扱い、過剰にrejectしない。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from benchmarks.schema.models import BenchmarkPerformance

_URL_RE = re.compile(r"^https?://[^\s]+$")


@dataclass
class ValidationIssue:
    field: str
    severity: str  # "error" | "warning"
    message: str


def _check_url(field_name: str, value: str | None) -> ValidationIssue | None:
    if value is None:
        return None
    if not _URL_RE.match(value):
        return ValidationIssue(field_name, "error", f"{field_name} はURL形式ではありません: {value!r}")
    return None


def validate_case(case: BenchmarkPerformance) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # --- 明確な物理的不整合(error) ---
    if case.regular_ticket_price < 0:
        issues.append(ValidationIssue("regular_ticket_price", "error", "ticket price が負数です"))
    if case.discount_ticket_price is not None and case.discount_ticket_price < 0:
        issues.append(ValidationIssue("discount_ticket_price", "error", "discount price が負数です"))
    if case.venue_capacity is not None and case.venue_capacity <= 0:
        issues.append(ValidationIssue("venue_capacity", "error", "capacity は正の整数である必要があります"))
    if case.performance_count is not None and case.performance_count <= 0:
        issues.append(ValidationIssue("performance_count", "error", "performance_count は正の整数である必要があります"))
    if case.run_end_date < case.run_start_date:
        issues.append(ValidationIssue("run_end_date", "error", "run_end_date が run_start_date より前です"))
    if case.venue_cost is not None and case.venue_cost < 0:
        issues.append(ValidationIssue("venue_cost", "error", "venue_cost が負数です"))

    if (
        case.observed_attendance is not None
        and case.venue_capacity is not None
        and case.performance_count is not None
        and case.observed_attendance_type.value == "exact"
        and case.observed_attendance > case.venue_capacity * case.performance_count
    ):
        issues.append(
            ValidationIssue(
                "observed_attendance",
                "error",
                "observed_attendance_type=exact なのに販売可能席数(capacity×公演回数)を超えています",
            )
        )

    # --- URL形式(error: 明確に不正な形式のみ) ---
    for field_name, value in (
        ("venue_capacity_source_url", case.venue_capacity_source_url),
        ("source_url", case.source_url),
    ):
        issue = _check_url(field_name, value)
        if issue:
            issues.append(issue)

    # --- future leakage(情報源の時系列矛盾。error) ---
    if (
        case.source_published_date is not None
        and case.retrieved_at is not None
        and case.source_published_date > case.retrieved_at
    ):
        issues.append(
            ValidationIssue(
                "retrieved_at",
                "error",
                "retrieved_at が source_published_date より前です(未来の情報を過去に取得したことになる)",
            )
        )

    # --- 判断が分かれうるもの(warning): 過剰にrejectしない ---
    if case.sold_out_status in ("all_sold_out", "partially_sold_out") and case.venue_capacity is None:
        issues.append(
            ValidationIssue(
                "venue_capacity",
                "warning",
                "完売系ステータスだが venue_capacity が欠損しているため lower-bound 評価ができません",
            )
        )
    if (
        case.sold_out_date is not None
        and case.ticket_sale_start_date is not None
        and case.sold_out_date < case.ticket_sale_start_date
    ):
        issues.append(
            ValidationIssue(
                "sold_out_date",
                "warning",
                "sold_out_date が ticket_sale_start_date より前です(データ誤記の可能性)",
            )
        )
    if (
        not case.is_synthetic
        and case.source_url is None
        and case.source_title is None
    ):
        issues.append(
            ValidationIssue(
                "source_url",
                "warning",
                "実在データにも関わらず情報源(source_url/source_title)が未記入です",
            )
        )
    if not case.is_synthetic and case.confidence is None:
        issues.append(
            ValidationIssue("confidence", "warning", "confidence(信頼度)が未設定です")
        )
    if case.performance_count is None:
        issues.append(
            ValidationIssue(
                "performance_count",
                "warning",
                "performance_countが不明のため、この公演はHistorical Backtestの対象・履歴の"
                "どちらにも使用できません(model_adapterで除外されます)",
            )
        )
    if case.excluded_from_standard_backtest and not case.exclusion_reason:
        issues.append(
            ValidationIssue(
                "exclusion_reason",
                "warning",
                "excluded_from_standard_backtest=Trueですがexclusion_reasonが未記入です",
            )
        )

    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == "error" for i in issues)
