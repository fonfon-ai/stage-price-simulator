"""Prediction Confidence / Data Sufficiency の評価ロジック(rule_v0.2で新規追加)。

Thin History / Cold Startへの対処方針は「価格をclampして問題を隠す」のではなく、
「使える過去実績が少ないほど、推奨の信頼度が低いことを明示する」というガードレールとして
実装する。DemandEstimator/PerformanceSimulator/Recommenderの計算結果そのものは変更しない
(数値を歪めない)。

rule_v0.1にも適用可能な独立コンポーネントであり、v0.1/v0.2どちらのパイプラインにも
後付けで組み合わせられる(Recommenderの変更は不要)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DataSufficiencyLevel(str, Enum):
    """使える過去実績(usable history)の件数に基づく信頼度区分。

    - LOW:    1件以下。単一の実績にbaseline_price・base_attendance_powerが
              全面的に依存するため、推奨価格が探索レンジの境界に張り付く等
              不安定になりやすい。
    - MEDIUM: 2件。まだ薄いが、極端な境界張り付きはLOWより起こりにくい。
    - NORMAL: 3件以上。通常の推奨として扱ってよい。
    """

    LOW = "low"
    MEDIUM = "medium"
    NORMAL = "normal"


def classify_data_sufficiency(usable_history_count: int) -> DataSufficiencyLevel:
    if usable_history_count <= 1:
        return DataSufficiencyLevel.LOW
    if usable_history_count == 2:
        return DataSufficiencyLevel.MEDIUM
    return DataSufficiencyLevel.NORMAL


@dataclass
class RecommendationReliability:
    data_sufficiency: DataSufficiencyLevel
    usable_history_count: int
    price_search_boundary_hit: bool
    warnings: list[str] = field(default_factory=list)

    @property
    def is_strong_recommendation_allowed(self) -> bool:
        """usable_history_count<=1の場合、単一の断定的な推奨(strong recommendation)は
        禁止し、必ずwarningsを伴う参考値として扱う。"""
        return self.data_sufficiency != DataSufficiencyLevel.LOW


def assess_recommendation_reliability(
    usable_history_count: int,
    balanced_price: int,
    price_min: int,
    price_max: int,
) -> RecommendationReliability:
    """推奨価格の信頼性を評価する。数値そのものは一切変更しない(clampしない)。"""
    level = classify_data_sufficiency(usable_history_count)
    boundary_hit = balanced_price in (price_min, price_max)

    warnings: list[str] = []
    if level == DataSufficiencyLevel.LOW:
        warnings.append(
            "usable_history_count<=1のため、この推奨は低信頼度(LOW)です。"
            "単一の過去実績にbaseline_price・基礎集客力が全面的に依存しており、"
            "価格推奨が不安定になりやすい状態です。"
        )
        if boundary_hit:
            warnings.append(
                "balanced_priceが価格探索レンジの境界(最低値または最高値)に一致しています。"
                "これは典型的なthin-history不安定化の兆候であり、この推奨を断定的な"
                "strong recommendationとして扱わないでください。"
            )
    elif level == DataSufficiencyLevel.MEDIUM:
        warnings.append(
            "usable_history_count=2のため、この推奨は中程度の信頼度(MEDIUM)です。"
        )
        if boundary_hit:
            warnings.append(
                "balanced_priceが価格探索レンジの境界に一致しています。履歴が少ない"
                "状態での境界張り付きのため、参考程度に留めてください。"
            )
    elif boundary_hit:
        # NORMALでも境界張り付き自体は情報として残す(無警告にしない)。
        warnings.append(
            "balanced_priceが価格探索レンジの境界に一致しています。探索レンジ自体を"
            "見直すか、他の推奨価格(満席重視/売上重視/利益重視)と合わせて確認してください。"
        )

    return RecommendationReliability(
        data_sufficiency=level,
        usable_history_count=usable_history_count,
        price_search_boundary_hit=boundary_hit,
        warnings=warnings,
    )
