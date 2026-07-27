"""Cross-organization Benchmark Diagnostics(集計・バケット分類ロジック)。

rule_v0.1・27係数は一切変更しない。ここではBenchmarkResultの集合を
performance_count・history depth・団体別にバケット分類し、横断比較できる統計量を
算出するだけの、純粋な集計処理のみを行う。

データが不足しているbucket/団体は該当統計をNone(レポート側でN/A表示)として返す。
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from benchmarks.scripts.metrics import BenchmarkResult

PERFORMANCE_COUNT_BUCKETS: list[tuple[str, int, int | None]] = [
    ("1", 1, 1),
    ("2-4", 2, 4),
    ("5-8", 5, 8),
    ("9-15", 9, 15),
    ("16-20", 16, 20),
    ("21+", 21, None),
]

HISTORY_DEPTH_BUCKETS: list[tuple[str, int, int | None]] = [
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4+", 4, None),
]


def bucket_performance_count(n: int | None) -> str | None:
    if n is None:
        return None
    for label, lo, hi in PERFORMANCE_COUNT_BUCKETS:
        if n >= lo and (hi is None or n <= hi):
            return label
    return None


def bucket_history_depth(n: int) -> str:
    for label, lo, hi in HISTORY_DEPTH_BUCKETS:
        if n >= lo and (hi is None or n <= hi):
            return label
    return "0"  # 理論上到達しない(usable_history_count>=1のみ評価対象になるため)


@dataclass
class BucketStats:
    label: str
    target_count: int = 0
    evaluated_count: int = 0
    skipped_count: int = 0
    sold_out_count: int = 0
    avg_predicted_demand_at_actual_price: float | None = None
    avg_predicted_demand_per_performance: float | None = None
    avg_actual_venue_capacity: float | None = None
    avg_demand_coverage_ratio: float | None = None
    sold_out_lower_bound_violation_rate: float | None = None
    price_search_boundary_hit_rate: float | None = None
    avg_price_gap: float | None = None
    avg_percentage_price_gap: float | None = None
    venue_fit_distribution: dict[str, int] = field(default_factory=dict)

    @property
    def has_evaluated_data(self) -> bool:
        return self.evaluated_count > 0


def _mean_or_none(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _rate_or_none(numerator_flags: list[bool]) -> float | None:
    return (sum(1 for f in numerator_flags if f) / len(numerator_flags)) if numerator_flags else None


def _compute_bucket_stats(label: str, results: list[BenchmarkResult]) -> BucketStats:
    evaluated = [r for r in results if r.status == "evaluated"]
    skipped = [r for r in results if r.status == "skipped"]
    sold_out_evaluated = [r for r in evaluated if r.sold_out_status == "all_sold_out"]

    venue_fit_dist: dict[str, int] = {}
    for r in evaluated:
        if r.venue_fit_at_actual_price:
            venue_fit_dist[r.venue_fit_at_actual_price] = (
                venue_fit_dist.get(r.venue_fit_at_actual_price, 0) + 1
            )

    return BucketStats(
        label=label,
        target_count=len(results),
        evaluated_count=len(evaluated),
        skipped_count=len(skipped),
        sold_out_count=sum(1 for r in results if r.sold_out_status == "all_sold_out"),
        avg_predicted_demand_at_actual_price=_mean_or_none(
            [r.predicted_demand_at_actual_price for r in evaluated
             if r.predicted_demand_at_actual_price is not None]
        ),
        avg_predicted_demand_per_performance=_mean_or_none(
            [r.predicted_demand_per_performance for r in evaluated
             if r.predicted_demand_per_performance is not None]
        ),
        avg_actual_venue_capacity=_mean_or_none(
            [r.actual_venue_capacity for r in evaluated if r.actual_venue_capacity is not None]
        ),
        avg_demand_coverage_ratio=_mean_or_none(
            [r.demand_coverage_ratio for r in sold_out_evaluated if r.demand_coverage_ratio is not None]
        ),
        sold_out_lower_bound_violation_rate=_rate_or_none(
            [bool(r.sold_out_lower_bound_violation) for r in sold_out_evaluated
             if r.sold_out_lower_bound_violation is not None]
        ),
        price_search_boundary_hit_rate=_rate_or_none(
            [bool(r.price_search_boundary_hit) for r in evaluated
             if r.price_search_boundary_hit is not None]
        ),
        avg_price_gap=_mean_or_none([r.price_gap for r in evaluated if r.price_gap is not None]),
        avg_percentage_price_gap=_mean_or_none(
            [r.percentage_price_gap for r in evaluated if r.percentage_price_gap is not None]
        ),
        venue_fit_distribution=venue_fit_dist,
    )


def aggregate_by_performance_count(results: list[BenchmarkResult]) -> dict[str, BucketStats]:
    """target公演をperformance_countでバケット分類して集計する。

    バケットの分類基準はtarget自身の`performance_count`(skippedでも既知なら分類可能)。
    """
    buckets: dict[str, list[BenchmarkResult]] = {label: [] for label, _, _ in PERFORMANCE_COUNT_BUCKETS}
    for r in results:
        label = bucket_performance_count(r.performance_count)
        if label is not None:
            buckets[label].append(r)
    return {label: _compute_bucket_stats(label, rs) for label, rs in buckets.items()}


def aggregate_by_history_depth(results: list[BenchmarkResult]) -> dict[str, BucketStats]:
    """evaluatedされたtargetをusable_history_count(=num_history_performances)で
    バケット分類して集計する(skippedはhistory不足で評価不能なため対象外)。
    """
    evaluated = [r for r in results if r.status == "evaluated"]
    buckets: dict[str, list[BenchmarkResult]] = {label: [] for label, _, _ in HISTORY_DEPTH_BUCKETS}
    for r in evaluated:
        label = bucket_history_depth(r.num_history_performances)
        buckets[label].append(r)
    return {label: _compute_bucket_stats(label, rs) for label, rs in buckets.items()}


@dataclass
class OrganizationStats:
    organization_name: str
    target_count: int = 0
    evaluated_count: int = 0
    avg_performance_count: float | None = None
    avg_usable_history_count: float | None = None
    avg_price_gap: float | None = None
    avg_percentage_price_gap: float | None = None
    avg_demand_coverage_ratio: float | None = None
    sold_out_lower_bound_violation_rate: float | None = None
    venue_fit_distribution: dict[str, int] = field(default_factory=dict)


def aggregate_by_organization(results: list[BenchmarkResult]) -> dict[str, OrganizationStats]:
    """団体別に集計する。「シソンヌ固有」か「複数公演モデル全般」かを横断比較するための集計。"""
    orgs = sorted({r.organization_name for r in results})
    stats: dict[str, OrganizationStats] = {}
    for org in orgs:
        org_results = [r for r in results if r.organization_name == org]
        evaluated = [r for r in org_results if r.status == "evaluated"]
        sold_out_evaluated = [r for r in evaluated if r.sold_out_status == "all_sold_out"]
        venue_fit_dist: dict[str, int] = {}
        for r in evaluated:
            if r.venue_fit_at_actual_price:
                venue_fit_dist[r.venue_fit_at_actual_price] = (
                    venue_fit_dist.get(r.venue_fit_at_actual_price, 0) + 1
                )
        stats[org] = OrganizationStats(
            organization_name=org,
            target_count=len(org_results),
            evaluated_count=len(evaluated),
            avg_performance_count=_mean_or_none(
                [r.performance_count for r in org_results if r.performance_count is not None]
            ),
            avg_usable_history_count=_mean_or_none(
                [float(r.num_history_performances) for r in evaluated]
            ),
            avg_price_gap=_mean_or_none([r.price_gap for r in evaluated if r.price_gap is not None]),
            avg_percentage_price_gap=_mean_or_none(
                [r.percentage_price_gap for r in evaluated if r.percentage_price_gap is not None]
            ),
            avg_demand_coverage_ratio=_mean_or_none(
                [r.demand_coverage_ratio for r in sold_out_evaluated
                 if r.demand_coverage_ratio is not None]
            ),
            sold_out_lower_bound_violation_rate=_rate_or_none(
                [bool(r.sold_out_lower_bound_violation) for r in sold_out_evaluated
                 if r.sold_out_lower_bound_violation is not None]
            ),
            venue_fit_distribution=venue_fit_dist,
        )
    return stats
