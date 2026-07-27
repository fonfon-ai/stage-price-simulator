"""BenchmarkPerformance を Production側の DemandEstimator / PerformanceSimulator /
Recommender にそのまま渡せる形へ変換するアダプタ。

重要: ここではモデルロジックを一切複製しない。RuleBasedDemandEstimator /
PerformanceSimulator / Recommender は backend/app/calculation の実装をそのまま呼び出す。
このファイルは「公開情報のスキーマ」→「Productionのdataclass」への変換のみを担う。

欠損値の扱い:
- 構造上どうしても必要な値(対象公演のvenue_capacity、履歴のtickets_sold相当)が
  欠損している場合は、値を捏造せずそのケースをスキップする。
- モデルが要求するがpublicデータで取得しづらい値(立地/ブランド評価、SNS等)は、
  「効果が中立(倍率1.0)になる」ことが数学的に保証されるニュートラル値のみを
  デフォルトとして使用し、どのフィールドをデフォルト適用したかを必ず記録する。
"""
from __future__ import annotations

from dataclasses import dataclass

from benchmarks.schema.models import BenchmarkPerformance, SoldOutStatus

from benchmarks.scripts import _bootstrap  # noqa: F401  (backend を sys.path に追加)

from app.calculation.types import (  # noqa: E402
    CurrentProductionInput,
    DemandFeatures,
    Genre,
    GroupInfo,
    PastPerformance,
    RarityLevel,
    VenueCandidate,
)

# --- ニュートラルデフォルト一覧 ---
# is_new_work/is_weekend_holiday/is_evening/has_guest/is_special:
#   すべて「False = 補正なし(倍率1.0)」がこのモデルの実装上の中立値。
# rarity_level:
#   RARITY_FACTOR["low"] == 1.00 が唯一の中立値。
# venue_walk_minutes / location_rating / brand_rating:
#   立地・ブランド補正には LOCATION_BASE=0.90 等、ベースからしてズレがあるため
#   厳密な意味での「倍率1.0」にはならない。ここでは評価3(中央値)・徒歩0分を
#   「最も判断を加えない値」として採用し、必ず defaulted_fields に記録する。
# venue_cost: 0円(不明な場合、profit=revenueとなることを結果側で明示する)。
# SNSフォロワー: 0(sns_factor=1.0が数学的に保証される)。
NEUTRAL_BOOL = False
NEUTRAL_RARITY = "low"
NEUTRAL_RATING = 3
NEUTRAL_WALK_MINUTES = 0
NEUTRAL_VENUE_COST = 0
NEUTRAL_SNS = 0

_ORG_TYPE_TO_GENRE = {
    "theatre": Genre.PLAY,
    "conte": Genre.CONTE,
    "comedy": Genre.CONTE,
    "other": Genre.OTHER,
}


@dataclass
class HistoryConversionResult:
    past_performances: list[PastPerformance]
    excluded_history_ids: list[str]  # tickets_soldが導出できず履歴として使えなかったbenchmark_id


@dataclass
class TargetConversionResult:
    features: DemandFeatures | None
    price_min: int
    price_max: int
    defaulted_fields: list[str]
    skip_reason: str | None  # Noneなら変換成功


def _derive_tickets_sold(case: BenchmarkPerformance) -> tuple[int | None, bool]:
    """観測値からモデルに渡す tickets_sold と sold_out flag を導出する。

    Production側の契約(docs/DATA_MODEL.md、demand_estimator.pyの `/ num_performances`)により、
    PastPerformance.tickets_sold は「そのrun全体(全performance_count回分)の合計販売枚数」で
    なければならない。1公演あたりの値(venue_capacity)をそのまま渡すと単位が壊れる
    (DEMAND_SEMANTICS_AUDIT.md #1参照)。

    捏造はしない: 値が導出できない場合は (None, False) を返し、呼び出し側で除外する。
    performance_countが不明な場合は「全公演完売」からrun全体合計を計算できないため、
    推測せずNoneを返す(呼び出し側でusable historyから除外される)。
    """
    sold_out = case.sold_out_status == SoldOutStatus.ALL_SOLD_OUT

    if case.observed_attendance is not None:
        return case.observed_attendance, sold_out

    # observed_attendanceが無くても、「全完売 かつ capacity既知 かつ performance_count既知」なら
    # venue_capacity × performance_count を run全体の需要下限として使う
    # (捏造ではなく、censored dataとして正当な下限。単一公演分のcapacityではなくrun全体合計)。
    if sold_out and case.venue_capacity is not None and case.performance_count is not None:
        return case.venue_capacity * case.performance_count, True

    return None, sold_out


def _days_before_sold_out(case: BenchmarkPerformance) -> int | None:
    if case.sold_out_date is None or case.ticket_sale_start_date is None:
        return None
    delta = (case.run_end_date - case.sold_out_date).days
    return max(0, delta)


def build_past_performances(history: list[BenchmarkPerformance]) -> HistoryConversionResult:
    """時系列上、対象公演より過去のBenchmarkPerformance群をPastPerformanceへ変換する。"""
    past_performances: list[PastPerformance] = []
    excluded: list[str] = []

    for h in history:
        if h.performance_count is None:
            # 公演回数が不明な履歴はPastPerformance.num_performancesを構築できないため、
            # 値を捏造せず除外する。
            excluded.append(h.benchmark_id)
            continue
        tickets_sold, sold_out = _derive_tickets_sold(h)
        if tickets_sold is None:
            excluded.append(h.benchmark_id)
            continue
        past_performances.append(
            PastPerformance(
                name=h.production_name,
                performance_date=h.run_start_date,
                # capacityはRuleBasedDemandEstimatorの計算式では未使用(過去実績の
                # 基礎集客力算出はtickets_sold/num_performancesのみに依存する)。
                # そのため未知の場合はtickets_soldをそのまま置く(数学的に無害な placeholder)。
                capacity=h.venue_capacity if h.venue_capacity is not None else tickets_sold,
                price=h.regular_ticket_price,
                num_performances=h.performance_count,
                tickets_sold=tickets_sold,
                sold_out=sold_out,
                days_before_sold_out=_days_before_sold_out(h),
                is_new_work=h.is_new_work if h.is_new_work is not None else NEUTRAL_BOOL,
                is_weekend_holiday=(
                    h.is_weekend_holiday if h.is_weekend_holiday is not None else NEUTRAL_BOOL
                ),
                is_evening=h.is_evening if h.is_evening is not None else NEUTRAL_BOOL,
                prefecture=h.prefecture,
                area=h.city,
                venue_name=h.venue_name,
            )
        )
    return HistoryConversionResult(past_performances=past_performances, excluded_history_ids=excluded)


def _price_search_range(actual_price: int) -> tuple[int, int]:
    """実売価格を中心とした便宜的な価格探索レンジ(モデル係数ではなく分析上の設定)。

    実売価格の50%〜180%を100円刻みに丸めて探索する。恣意的だが、係数(PRICE_ELASTICITY等)
    には一切影響しない、価格探索の「探索範囲」の設定に過ぎない。
    """
    price_min = max(100, round(actual_price * 0.5 / 100) * 100)
    price_max = max(price_min + 100, round(actual_price * 1.8 / 100) * 100)
    return price_min, price_max


def build_target_features(
    target: BenchmarkPerformance, past_performances: list[PastPerformance]
) -> TargetConversionResult:
    """評価対象(target)公演を DemandFeatures へ変換する。"""
    defaulted_fields: list[str] = []
    price_min, price_max = _price_search_range(target.regular_ticket_price)

    if not past_performances:
        return TargetConversionResult(
            features=None, price_min=price_min, price_max=price_max,
            defaulted_fields=defaulted_fields,
            skip_reason="no_usable_history",
        )

    if target.venue_capacity is None:
        return TargetConversionResult(
            features=None, price_min=price_min, price_max=price_max,
            defaulted_fields=defaulted_fields,
            skip_reason="missing_target_venue_capacity",
        )

    if target.performance_count is None:
        return TargetConversionResult(
            features=None, price_min=price_min, price_max=price_max,
            defaulted_fields=defaulted_fields,
            skip_reason="missing_target_performance_count",
        )

    def _default(value, default, field_name):
        if value is None:
            defaulted_fields.append(field_name)
            return default
        return value

    group = GroupInfo(
        name=target.organization_name,
        genre=_ORG_TYPE_TO_GENRE.get(target.organization_type.value, Genre.OTHER),
        years_active=_default(target.years_active, 0, "years_active"),
        sns_x_followers=_default(target.sns_x_followers, NEUTRAL_SNS, "sns_x_followers"),
        sns_instagram_followers=_default(
            target.sns_instagram_followers, NEUTRAL_SNS, "sns_instagram_followers"
        ),
        sns_youtube_subscribers=_default(
            target.sns_youtube_subscribers, NEUTRAL_SNS, "sns_youtube_subscribers"
        ),
        sns_other_followers=_default(
            target.sns_other_followers, NEUTRAL_SNS, "sns_other_followers"
        ),
    )

    rarity_str = target.rarity_level or NEUTRAL_RARITY
    if target.rarity_level is None:
        defaulted_fields.append("rarity_level")

    current_production = CurrentProductionInput(
        area=target.prefecture,
        performance_date=target.run_start_date,
        is_new_work=_default(target.is_new_work, NEUTRAL_BOOL, "is_new_work"),
        is_weekend_holiday=_default(target.is_weekend_holiday, NEUTRAL_BOOL, "is_weekend_holiday"),
        is_evening=_default(target.is_evening, NEUTRAL_BOOL, "is_evening"),
        rarity_level=RarityLevel(rarity_str),
        has_guest=_default(target.has_guest, NEUTRAL_BOOL, "has_guest"),
        is_special=_default(target.is_special, NEUTRAL_BOOL, "is_special"),
        price_min=price_min,
        price_max=price_max,
    )

    venue = VenueCandidate(
        name=target.venue_name,
        area=target.prefecture,
        capacity=target.venue_capacity,
        venue_cost=_default(target.venue_cost, NEUTRAL_VENUE_COST, "venue_cost"),
        walk_minutes=_default(target.venue_walk_minutes, NEUTRAL_WALK_MINUTES, "venue_walk_minutes"),
        location_rating=_default(
            target.venue_location_rating, NEUTRAL_RATING, "venue_location_rating"
        ),
        brand_rating=_default(target.venue_brand_rating, NEUTRAL_RATING, "venue_brand_rating"),
    )

    features = DemandFeatures(
        group=group,
        past_performances=past_performances,
        current_production=current_production,
        venue=venue,
        price=target.regular_ticket_price,
        num_performances=target.performance_count,
    )
    return TargetConversionResult(
        features=features, price_min=price_min, price_max=price_max,
        defaulted_fields=defaulted_fields, skip_reason=None,
    )
