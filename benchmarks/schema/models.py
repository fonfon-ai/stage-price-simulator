"""External Benchmark用データスキーマ。

公開情報から収集した実在公演データを表現するための dataclass 群。
Production側(backend/app)には一切依存しない、独立したスキーマ定義。

方針:
- 欠損値は null(None)/"unknown" を正式に許容する。推測で埋めない。
- venue_capacity は時系列データとして扱い、取得元と有効時点をセットで保持する。
- すべての外部データにsource provenance(情報源)を保持する。
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, fields
from enum import Enum


class OrganizationType(str, Enum):
    THEATRE = "theatre"
    CONTE = "conte"
    COMEDY = "comedy"
    OTHER = "other"


class SoldOutStatus(str, Enum):
    ALL_SOLD_OUT = "all_sold_out"
    PARTIALLY_SOLD_OUT = "partially_sold_out"
    NOT_SOLD_OUT = "not_sold_out"
    UNKNOWN = "unknown"


class AttendanceType(str, Enum):
    """observed_attendance の性質。

    EXACT: 主催者等が公表した正確な実売数。
    REPORTED_TOTAL: 「〇〇人動員」等、正確性が保証されない報告値。
    LOWER_BOUND: 「完売」等からしか分からず、実際の需要はこれ以上である下限値。
    UNKNOWN: 値そのものが取得できない。
    """

    EXACT = "exact"
    REPORTED_TOTAL = "reported_total"
    LOWER_BOUND = "lower_bound"
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    OFFICIAL_ORGANIZATION = "official_organization"
    OFFICIAL_VENUE = "official_venue"
    OFFICIAL_AGENCY = "official_agency"
    OFFICIAL_TICKET = "official_ticket"
    MEDIA = "media"
    SECONDARY = "secondary"


class ConfidenceLevel(str, Enum):
    """情報の信頼度。

    A: 主催者・劇団・芸人・劇場等の公式一次情報。
    B: チケット会社・信頼できる興行情報(公式一次情報ではないが業界的に信頼度が高い)。
    C: ニュース・二次情報(伝聞・まとめ記事等、裏取りが弱いもの)。
    """

    A = "A"
    B = "B"
    C = "C"


def _opt_int(v):
    return None if v in (None, "") else int(v)


def _opt_float(v):
    return None if v in (None, "") else float(v)


def _opt_bool(v):
    if v in (None, ""):
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def _opt_date(v):
    if v in (None, ""):
        return None
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v))


def _opt_str(v):
    return None if v in (None, "") else str(v)


@dataclass
class BenchmarkPerformance:
    """1公演(run)分のExternal Benchmarkレコード。"""

    # --- 必須項目(最低限保持すべき項目) ---
    benchmark_id: str
    organization_name: str
    organization_type: OrganizationType
    production_name: str
    run_start_date: dt.date
    run_end_date: dt.date
    prefecture: str
    city: str
    venue_name: str
    regular_ticket_price: int
    sold_out_status: SoldOutStatus
    observed_attendance_type: AttendanceType

    # --- 公演回数: 実務上、公開情報から正確な公演回数が特定できないケースがあるため
    #     (例: 途中でスケジュールが変更された、公式が総回数を明記していない等)Optionalとする。
    #     欠損の場合、その公演はHistorical Backtestの対象・履歴の両方から除外する
    #     (model_adapter.py参照。捏造はしない)。
    #
    #     単位契約: 「対象run(この benchmark_id が表す公演期間)に含まれる公演回数」。
    #     Production側 DemandFeatures.num_performances / PastPerformance.num_performances と
    #     同一の単位(DEMAND_SEMANTICS_AUDIT.md参照)。ツアーの一部地域のみを表す行の場合、
    #     ツアー全体の公演回数ではなく、その行が表す地域・会場の公演回数のみを入れること。
    performance_count: int | None = None

    # --- venue capacityは時系列データとして扱う(現在値を一律適用しない) ---
    #     単位契約: 「1公演あたりの物理的または販売可能な客席数」(run全体の延べ席数ではない)。
    #     Production側 VenueCandidate.capacity / PastPerformance.capacity と同一の単位。
    #     興行全体の延べ販売可能席数が必要な箇所では、必ず venue_capacity × performance_count
    #     を計算すること(venue_capacity単体をrun全体の値として扱ってはならない)。
    venue_capacity: int | None = None
    venue_capacity_source_url: str | None = None
    venue_capacity_effective_date: dt.date | None = None
    capacity_confidence: str | None = None  # 例: "confirmed_for_this_run" / "estimated_from_current" / "unknown"

    # --- 価格・完売関連(欠損許容) ---
    discount_ticket_price: int | None = None
    ticket_sale_start_date: dt.date | None = None
    sold_out_date: dt.date | None = None

    # 単位契約: 「対象run全体(performance_count回分の合計)の総販売枚数/総来場数」。
    # 1公演あたりの人数ではない。Production側 PastPerformanceSale.tickets_sold /
    # PastPerformance.tickets_sold と同一の単位(docs/DATA_MODEL.md、
    # docs/DEMAND_SEMANTICS_AUDIT.md参照)。observed_attendance_type=lower_boundの場合、
    # この値は「run全体の総販売枚数の下限」を意味する(例: 全performance_count回完売なら
    # venue_capacity × performance_count が正しい下限。venue_capacity単体ではない)。
    observed_attendance: int | None = None

    # --- Production側モデルを動かすための補助特徴量(公開情報で取れないことが多いため全てOptional) ---
    is_new_work: bool | None = None
    is_weekend_holiday: bool | None = None
    is_evening: bool | None = None
    rarity_level: str | None = None  # low/mid/high
    has_guest: bool | None = None
    is_special: bool | None = None
    venue_walk_minutes: int | None = None
    venue_location_rating: int | None = None
    venue_brand_rating: int | None = None
    venue_cost: int | None = None
    sns_x_followers: int | None = None
    sns_instagram_followers: int | None = None
    sns_youtube_subscribers: int | None = None
    sns_other_followers: int | None = None
    years_active: int | None = None

    # --- Source Provenance(情報源) ---
    source_url: str | None = None
    source_title: str | None = None
    source_publisher: str | None = None
    source_published_date: dt.date | None = None
    retrieved_at: dt.date | None = None
    source_type: SourceType | None = None
    confidence: ConfidenceLevel | None = None

    # --- メタ ---
    is_synthetic: bool = False
    notes: str | None = None

    # --- 特殊条件フラグ(COVID等、通常のHistorical Backtestに混入させたくない公演) ---
    # notesにCOVID等の特殊事情が記載されている場合でも自動判定はせず、この列で明示的に
    # 管理する。Trueの場合、run_backtest.pyの「標準」実行では対象・履歴の両方から除外される。
    excluded_from_standard_backtest: bool = False
    exclusion_reason: str | None = None  # 例: "covid_era_capacity_restriction"

    @staticmethod
    def from_row(row: dict) -> "BenchmarkPerformance":
        """CSVの1行(dict[str, str])からBenchmarkPerformanceを構築する。"""
        return BenchmarkPerformance(
            benchmark_id=row["benchmark_id"],
            organization_name=row["organization_name"],
            organization_type=OrganizationType(row["organization_type"]),
            production_name=row["production_name"],
            run_start_date=dt.date.fromisoformat(row["run_start_date"]),
            run_end_date=dt.date.fromisoformat(row["run_end_date"]),
            prefecture=row.get("prefecture", "") or "",
            city=row.get("city", "") or "",
            venue_name=row["venue_name"],
            performance_count=_opt_int(row.get("performance_count")),
            regular_ticket_price=int(row["regular_ticket_price"]),
            sold_out_status=SoldOutStatus(row.get("sold_out_status") or "unknown"),
            observed_attendance_type=AttendanceType(row.get("observed_attendance_type") or "unknown"),
            venue_capacity=_opt_int(row.get("venue_capacity")),
            venue_capacity_source_url=_opt_str(row.get("venue_capacity_source_url")),
            venue_capacity_effective_date=_opt_date(row.get("venue_capacity_effective_date")),
            capacity_confidence=_opt_str(row.get("capacity_confidence")),
            discount_ticket_price=_opt_int(row.get("discount_ticket_price")),
            ticket_sale_start_date=_opt_date(row.get("ticket_sale_start_date")),
            sold_out_date=_opt_date(row.get("sold_out_date")),
            observed_attendance=_opt_int(row.get("observed_attendance")),
            is_new_work=_opt_bool(row.get("is_new_work")),
            is_weekend_holiday=_opt_bool(row.get("is_weekend_holiday")),
            is_evening=_opt_bool(row.get("is_evening")),
            rarity_level=_opt_str(row.get("rarity_level")),
            has_guest=_opt_bool(row.get("has_guest")),
            is_special=_opt_bool(row.get("is_special")),
            venue_walk_minutes=_opt_int(row.get("venue_walk_minutes")),
            venue_location_rating=_opt_int(row.get("venue_location_rating")),
            venue_brand_rating=_opt_int(row.get("venue_brand_rating")),
            venue_cost=_opt_int(row.get("venue_cost")),
            sns_x_followers=_opt_int(row.get("sns_x_followers")),
            sns_instagram_followers=_opt_int(row.get("sns_instagram_followers")),
            sns_youtube_subscribers=_opt_int(row.get("sns_youtube_subscribers")),
            sns_other_followers=_opt_int(row.get("sns_other_followers")),
            years_active=_opt_int(row.get("years_active")),
            source_url=_opt_str(row.get("source_url")),
            source_title=_opt_str(row.get("source_title")),
            source_publisher=_opt_str(row.get("source_publisher")),
            source_published_date=_opt_date(row.get("source_published_date")),
            retrieved_at=_opt_date(row.get("retrieved_at")),
            source_type=SourceType(row["source_type"]) if row.get("source_type") else None,
            confidence=ConfidenceLevel(row["confidence"]) if row.get("confidence") else None,
            is_synthetic=_opt_bool(row.get("is_synthetic")) or False,
            notes=_opt_str(row.get("notes")),
            excluded_from_standard_backtest=_opt_bool(row.get("excluded_from_standard_backtest"))
            or False,
            exclusion_reason=_opt_str(row.get("exclusion_reason")),
        )

    def to_row(self) -> dict:
        """CSV書き出し用にdict[str, str]へ変換する(Noneは空文字列)。"""

        def s(v):
            if v is None:
                return ""
            if isinstance(v, Enum):
                return v.value
            return str(v)

        return {col: s(getattr(self, col)) for col in CSV_COLUMNS}


CSV_COLUMNS = [f.name for f in fields(BenchmarkPerformance)]
