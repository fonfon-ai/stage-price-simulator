"""Backtestペア(target + history)からProduction側のDemandEstimator/PerformanceSimulator/
Recommenderを呼び出し、比較指標を計算する。

繰り返しになるが、ここでは既存モデルロジックを一切複製せず、backend/app/calculation の
実装をそのまま呼び出す。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from benchmarks.schema.models import SoldOutStatus
from benchmarks.scripts import _bootstrap  # noqa: F401
from benchmarks.scripts.backtest import BacktestPair
from benchmarks.scripts.model_adapter import build_past_performances, build_target_features

from app.calculation import constants as calc_constants  # noqa: E402
from app.calculation.confidence import assess_recommendation_reliability  # noqa: E402
from app.calculation.demand_estimator import DemandEstimator, RuleBasedDemandEstimator  # noqa: E402
from app.calculation.recommender import recommend, run_full_search  # noqa: E402
from app.calculation.simulator import PerformanceSimulator  # noqa: E402

RESULT_CSV_COLUMNS = [
    "benchmark_id",
    "organization_name",
    "production_name",
    "model_version",
    "status",  # "evaluated" | "skipped"
    "skip_reason",
    "performance_count",
    "num_history_performances",  # = usable_history_count(履歴として実際に使えた件数)
    "excluded_history_ids",
    "defaulted_fields",
    "actual_ticket_price",
    "recommended_price_low",
    "recommended_price_high",
    "balanced_price",
    "revenue_price",
    "profit_price",
    "price_search_boundary_hit",
    "actual_venue_capacity",
    "recommended_capacity_low",
    "recommended_capacity_high",
    "venue_fit_at_actual_price",
    "predicted_demand_at_actual_price",
    "predicted_demand_per_performance",
    "demand_per_performance_to_capacity_ratio",
    "demand_coverage_ratio",
    "sold_out_status",
    "sold_out_lower_bound_violation",
    "price_gap",
    "percentage_price_gap",
    "data_sufficiency",
    "is_strong_recommendation_allowed",
    "reliability_warnings",
]


@dataclass
class BenchmarkResult:
    benchmark_id: str
    organization_name: str
    production_name: str
    model_version: str
    status: str
    skip_reason: str | None = None
    performance_count: int | None = None
    num_history_performances: int = 0
    excluded_history_ids: list[str] = field(default_factory=list)
    defaulted_fields: list[str] = field(default_factory=list)
    actual_ticket_price: int | None = None
    recommended_price_low: int | None = None
    recommended_price_high: int | None = None
    balanced_price: int | None = None
    revenue_price: int | None = None
    profit_price: int | None = None
    price_search_boundary_hit: bool | None = None
    actual_venue_capacity: int | None = None
    recommended_capacity_low: int | None = None
    recommended_capacity_high: int | None = None
    venue_fit_at_actual_price: str | None = None
    predicted_demand_at_actual_price: float | None = None
    predicted_demand_per_performance: float | None = None
    demand_per_performance_to_capacity_ratio: float | None = None
    demand_coverage_ratio: float | None = None
    sold_out_status: str | None = None
    sold_out_lower_bound_violation: bool | None = None
    price_gap: int | None = None
    percentage_price_gap: float | None = None
    data_sufficiency: str | None = None
    is_strong_recommendation_allowed: bool | None = None
    reliability_warnings: list[str] = field(default_factory=list)

    def to_row(self) -> dict:
        def s(v):
            if v is None:
                return ""
            if isinstance(v, list):
                return "|".join(v)
            return v

        return {col: s(getattr(self, col)) for col in RESULT_CSV_COLUMNS}


def _per_performance_demand(estimator: DemandEstimator, features, price: int) -> float:
    """Production側の既存ロジック(RuleBasedDemandEstimator.estimate_demand)をそのまま再利用し、
    「1公演あたり」単位の需要を得る。

    demand_estimator.py の契約上、`total_expected_demand = expected_demand_per_performance *
    (num_performances ** POOL_EXPONENT)` であり、`num_performances=1` を渡すと
    `1 ** POOL_EXPONENT == 1` となるため `total_expected_demand` はそのまま
    `expected_demand_per_performance` と一致する。POOL_EXPONENT等の数式をBenchmark側で
    複製せず、estimate_demand() をnum_performances=1で呼び出すことで同じ結果を得る。
    """
    single_performance_features = dataclasses.replace(features, price=price, num_performances=1)
    return estimator.estimate_demand(single_performance_features).total_expected_demand


def evaluate_pair(
    pair: BacktestPair,
    estimator: DemandEstimator | None = None,
    model_version: str | None = None,
) -> BenchmarkResult:
    """Backtestペアを評価する。

    `estimator`/`model_version`を指定しない場合はrule_v0.1(既定動作、後方互換)。
    rule_v0.2等の別バージョンを評価する場合は、呼び出し側で該当の
    DemandEstimator実装とモデルバージョン文字列を明示的に渡す
    (`benchmarks/scripts/model_registry.py`参照)。ここではモデルロジックを
    一切複製せず、渡されたestimatorをそのまま呼び出すだけである。
    """
    target = pair.target
    if estimator is None:
        estimator = RuleBasedDemandEstimator()
    if model_version is None:
        model_version = calc_constants.MODEL_VERSION

    history_conv = build_past_performances(pair.history)

    if not history_conv.past_performances:
        return BenchmarkResult(
            benchmark_id=target.benchmark_id,
            organization_name=target.organization_name,
            production_name=target.production_name,
            model_version=model_version,
            status="skipped",
            skip_reason="no_usable_history",
            performance_count=target.performance_count,
            num_history_performances=0,
            excluded_history_ids=history_conv.excluded_history_ids,
            sold_out_status=target.sold_out_status.value,
        )

    target_conv = build_target_features(target, history_conv.past_performances)

    if target_conv.skip_reason is not None:
        return BenchmarkResult(
            benchmark_id=target.benchmark_id,
            organization_name=target.organization_name,
            production_name=target.production_name,
            model_version=model_version,
            status="skipped",
            skip_reason=target_conv.skip_reason,
            performance_count=target.performance_count,
            num_history_performances=len(history_conv.past_performances),
            excluded_history_ids=history_conv.excluded_history_ids,
            sold_out_status=target.sold_out_status.value,
        )

    assert target_conv.features is not None  # skip_reasonがNoneならfeaturesは必ず構築されている
    features = target_conv.features
    simulator = PerformanceSimulator(estimator)

    reference_estimate = estimator.estimate_demand(features)
    scenarios = run_full_search(
        simulator,
        features,
        [features.venue],
        [features.num_performances],
        target_conv.price_min,
        target_conv.price_max,
    )
    rec = recommend(scenarios, reference_estimate.baseline_price)

    actual_scenario = simulator.simulate(
        features, features.venue, target.regular_ticket_price, features.num_performances
    )

    # recommended_capacity_low/highは1公演あたり単位(actual_venue_capacityと同一単位)で
    # 算出する必要がある。rec.balance_scenario.expected_demand は興行全体(run全体)単位のため、
    # そのまま使うと単位が壊れる(DEMAND_SEMANTICS_AUDIT.md #2参照)。
    # Production側のPOOL_EXPONENTロジックを複製せず、estimate_demand()をnum_performances=1で
    # 再呼び出しすることで「1公演あたり需要」を得る。
    balance_per_performance_demand = _per_performance_demand(
        estimator, features, rec.balance_scenario.price
    )
    capacity_low = round(balance_per_performance_demand / 1.0)
    capacity_high = round(balance_per_performance_demand / calc_constants.VENUE_FIT_GOOD_MIN)

    sold_out_violation = None
    demand_coverage_ratio = None
    if target.sold_out_status == SoldOutStatus.ALL_SOLD_OUT:
        sold_out_violation = actual_scenario.expected_demand < actual_scenario.available_seats
        # demand_coverage_ratio = predicted_total_demand / sold_out_lower_bound(=available_seats)。
        # 1.0未満なら「全公演完売」という公開情報と矛盾する。
        if actual_scenario.available_seats > 0:
            demand_coverage_ratio = actual_scenario.expected_demand / actual_scenario.available_seats

    price_gap = rec.balance_price - target.regular_ticket_price
    percentage_price_gap = (
        price_gap / target.regular_ticket_price * 100 if target.regular_ticket_price else None
    )

    # price_search_boundary_hit: 推奨価格(balanced_price)が探索レンジの最低値/最高値と
    # 一致した場合、探索範囲の境界に張り付いた(=データが薄く不安定な可能性がある)ことを示す。
    price_search_boundary_hit = rec.balance_price in (target_conv.price_min, target_conv.price_max)

    # predicted_demand_per_performance: Production側の既存ロジック(num_performances=1)を
    # そのまま再利用して算出する「1公演あたり需要」。新しい計算式は作らない。
    predicted_demand_per_performance = _per_performance_demand(
        estimator, features, target.regular_ticket_price
    )
    demand_per_performance_to_capacity_ratio = (
        predicted_demand_per_performance / target.venue_capacity
        if target.venue_capacity
        else None
    )

    # Prediction Confidence / Data Sufficiency(rule_v0.2で導入したガードレール層)。
    # v0.1のRecommender自体は変更していないため、この評価はv0.1/v0.2どちらのestimatorを
    # 使った場合でも同じロジックで後付けできる独立コンポーネントである。
    reliability = assess_recommendation_reliability(
        usable_history_count=len(history_conv.past_performances),
        balanced_price=rec.balance_price,
        price_min=target_conv.price_min,
        price_max=target_conv.price_max,
    )

    return BenchmarkResult(
        benchmark_id=target.benchmark_id,
        organization_name=target.organization_name,
        production_name=target.production_name,
        model_version=model_version,
        status="evaluated",
        skip_reason=None,
        performance_count=target.performance_count,
        num_history_performances=len(history_conv.past_performances),
        excluded_history_ids=history_conv.excluded_history_ids,
        defaulted_fields=target_conv.defaulted_fields,
        actual_ticket_price=target.regular_ticket_price,
        recommended_price_low=rec.recommended_price_range[0],
        recommended_price_high=rec.recommended_price_range[1],
        balanced_price=rec.balance_price,
        revenue_price=rec.revenue_price,
        profit_price=rec.profit_price,
        price_search_boundary_hit=price_search_boundary_hit,
        actual_venue_capacity=target.venue_capacity,
        recommended_capacity_low=capacity_low,
        recommended_capacity_high=capacity_high,
        venue_fit_at_actual_price=actual_scenario.venue_fit.value,
        predicted_demand_at_actual_price=actual_scenario.expected_demand,
        predicted_demand_per_performance=predicted_demand_per_performance,
        demand_per_performance_to_capacity_ratio=demand_per_performance_to_capacity_ratio,
        demand_coverage_ratio=demand_coverage_ratio,
        sold_out_status=target.sold_out_status.value,
        sold_out_lower_bound_violation=sold_out_violation,
        price_gap=price_gap,
        percentage_price_gap=percentage_price_gap,
        data_sufficiency=reliability.data_sufficiency.value,
        is_strong_recommendation_allowed=reliability.is_strong_recommendation_allowed,
        reliability_warnings=reliability.warnings,
    )
