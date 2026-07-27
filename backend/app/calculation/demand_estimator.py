"""需要推定コンポーネント。将来 MLDemandEstimator に差し替え可能なインターフェース設計。

詳細な根拠は docs/CALCULATION_LOGIC.md を参照。
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

from app.calculation import constants as c
from app.calculation.types import DemandEstimate, DemandFeatures, ExplanationItem, PastPerformance


class DemandEstimator(ABC):
    """需要推定の抽象インターフェース。MVPはルールベース、将来MLモデルに差し替え可能。"""

    @abstractmethod
    def estimate_demand(self, features: DemandFeatures) -> DemandEstimate:
        raise NotImplementedError


def _corrected_attendance(perf: PastPerformance) -> float:
    """完売公演の censored data 補正（実売 >= 真の需要 の下限であることの補正）。"""
    if not perf.sold_out:
        return float(perf.tickets_sold)
    days = perf.days_before_sold_out or 0
    factor = c.SOLD_OUT_BASE_CORRECTION + min(
        c.SOLD_OUT_CORRECTION_CAP - c.SOLD_OUT_BASE_CORRECTION,
        days * c.SOLD_OUT_EARLY_BONUS_PER_DAY,
    )
    return perf.tickets_sold * factor


def _weights(n: int) -> list[float]:
    """直近を最重視する指数減衰の重み（正規化前）。past_performancesは新しい順を想定。"""
    raw = [c.ATTENDANCE_DECAY**i for i in range(n)]
    total = sum(raw)
    return [w / total for w in raw]


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class RuleBasedDemandEstimator(DemandEstimator):
    """MVP実装。ルールベースの乗算モデルで需要を推定する。"""

    def estimate_demand(self, features: DemandFeatures) -> DemandEstimate:
        explanation: list[ExplanationItem] = []

        past_sorted = sorted(
            features.past_performances, key=lambda p: p.performance_date, reverse=True
        )
        if not past_sorted:
            raise ValueError("At least one past performance is required to estimate demand.")

        weights = _weights(len(past_sorted))
        per_perf_attendance = [
            _corrected_attendance(p) / max(1, p.num_performances) for p in past_sorted
        ]
        base_attendance_power = sum(w * a for w, a in zip(weights, per_perf_attendance))
        baseline_price = sum(w * p.price for w, p in zip(weights, past_sorted))

        explanation.append(
            ExplanationItem(
                factor="base_attendance_power",
                multiplier=1.0,
                description=(
                    f"過去{len(past_sorted)}公演の加重平均動員(直近を重視): "
                    f"{base_attendance_power:.0f}人/公演"
                ),
            )
        )

        demand = base_attendance_power

        # 価格補正
        relative_change = (
            (features.price - baseline_price) / baseline_price if baseline_price else 0.0
        )
        price_factor = _clip(
            math.exp(-c.PRICE_ELASTICITY * relative_change),
            c.PRICE_FACTOR_MIN,
            c.PRICE_FACTOR_MAX,
        )
        demand *= price_factor
        pct = relative_change * 100
        explanation.append(
            ExplanationItem(
                factor="price",
                multiplier=price_factor,
                description=(
                    f"過去平均価格({baseline_price:.0f}円)に対し価格を{pct:+.0f}%設定 "
                    f"→ 需要{(price_factor - 1) * 100:+.1f}%"
                ),
            )
        )

        cp = features.current_production

        if cp.is_weekend_holiday:
            demand *= c.WEEKEND_HOLIDAY_FACTOR
            explanation.append(
                ExplanationItem(
                    "weekend_holiday", c.WEEKEND_HOLIDAY_FACTOR, "土日祝のため需要+8%"
                )
            )
        if cp.is_evening:
            demand *= c.EVENING_FACTOR
            explanation.append(ExplanationItem("evening", c.EVENING_FACTOR, "夜公演のため需要+5%"))
        if cp.is_new_work:
            demand *= c.NEW_WORK_FACTOR
            explanation.append(ExplanationItem("new_work", c.NEW_WORK_FACTOR, "新作のため需要+5%"))

        rarity_factor = c.RARITY_FACTOR[cp.rarity_level.value]
        if rarity_factor != 1.0:
            demand *= rarity_factor
            explanation.append(
                ExplanationItem(
                    "rarity", rarity_factor, f"希少性({cp.rarity_level.value})により需要変動"
                )
            )
        if cp.has_guest:
            demand *= c.GUEST_FACTOR
            explanation.append(ExplanationItem("guest", c.GUEST_FACTOR, "ゲスト出演により需要+7%"))
        if cp.is_special:
            demand *= c.SPECIAL_FACTOR
            explanation.append(
                ExplanationItem("special", c.SPECIAL_FACTOR, "特別公演のため需要+10%")
            )

        venue = features.venue
        location_factor = _clip(
            c.LOCATION_BASE
            + c.LOCATION_RATING_STEP * (venue.location_rating - 3)
            - c.LOCATION_WALK_PENALTY_PER_MIN * venue.walk_minutes,
            c.LOCATION_FACTOR_MIN,
            c.LOCATION_FACTOR_MAX,
        )
        demand *= location_factor
        explanation.append(
            ExplanationItem(
                "location",
                location_factor,
                f"立地評価{venue.location_rating}・徒歩{venue.walk_minutes}分による補正",
            )
        )

        brand_factor = _clip(
            c.BRAND_BASE + c.BRAND_RATING_STEP * (venue.brand_rating - 3),
            c.BRAND_FACTOR_MIN,
            c.BRAND_FACTOR_MAX,
        )
        demand *= brand_factor
        explanation.append(
            ExplanationItem(
                "venue_brand", brand_factor, f"会場ブランド評価{venue.brand_rating}による補正"
            )
        )

        weighted_followers = (
            features.group.sns_x_followers * c.SNS_WEIGHT_X
            + features.group.sns_instagram_followers * c.SNS_WEIGHT_INSTAGRAM
            + features.group.sns_youtube_subscribers * c.SNS_WEIGHT_YOUTUBE
            + features.group.sns_other_followers * c.SNS_WEIGHT_OTHER
        )
        sns_score = math.log1p(weighted_followers)
        sns_factor = 1 + min(c.SNS_FACTOR_CAP, c.SNS_FACTOR_SCALE * sns_score)
        demand *= sns_factor
        explanation.append(
            ExplanationItem(
                "sns",
                sns_factor,
                f"SNS補助指標(補助情報、上限+{c.SNS_FACTOR_CAP * 100:.0f}%): "
                f"需要{(sns_factor - 1) * 100:+.1f}%",
            )
        )

        expected_demand_per_performance = demand
        total_expected_demand = expected_demand_per_performance * (
            features.num_performances**c.POOL_EXPONENT
        )
        if features.num_performances > 1:
            explanation.append(
                ExplanationItem(
                    "performance_count_pool",
                    features.num_performances**c.POOL_EXPONENT / features.num_performances,
                    f"公演回数{features.num_performances}回のため観客プール逓減モデルを適用",
                )
            )

        return DemandEstimate(
            base_attendance_power=base_attendance_power,
            baseline_price=baseline_price,
            expected_demand_per_performance=expected_demand_per_performance,
            total_expected_demand=total_expected_demand,
            explanation=explanation,
        )
