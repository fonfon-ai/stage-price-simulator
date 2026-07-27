"""[EXPERIMENTAL] rule_v0.2 — NOT the production default.

Production defaultは引き続き rule_v0.1(`RuleBasedDemandEstimator`)。rule_v0.2は
Historical Benchmarkでの比較・評価専用のセカンドモデルであり、FastAPIの本番エンドポイント
からは呼び出されていない。Production昇格の判定はNOT ENOUGH DATA(docs/RULE_V0_2_EVALUATION.md、
再評価条件はREADME.md「Phase 2 TODO」参照)。

rule_v0.2: Multi-performance Demand Scalingを

    Core Audience(1公演あたり基礎需要)
  × Accessibility Gain(公演回数による到達可能顧客の増加)
  × Cannibalization(観客プールの重複による逓減)

の3概念に構造分離したDemandEstimator。

rule_v0.1(`RuleBasedDemandEstimator`)は一切変更しない。本クラスは内部でv0.1の
estimate_demand()をそのまま呼び出し、価格・曜日・新作/再演・希少性・ゲスト・特別公演・
立地・会場ブランド・SNS補正・completed data補正・直近重視の加重平均という27係数ロジックを
そのまま再利用する。変更するのは「1公演あたり需要 → 興行全体需要」への変換ステップのみ。

設計根拠: docs/RULE_V0_2_DESIGN.md
"""
from __future__ import annotations

from app.calculation import constants_v2 as c2
from app.calculation.demand_estimator import DemandEstimator, RuleBasedDemandEstimator
from app.calculation.types import DemandEstimate, DemandFeatures, ExplanationItem


def accessibility_gain(num_performances: int) -> float:
    """公演回数nに対するAccessibility Gain(区分: heuristic、docs/RULE_V0_2_DESIGN.md参照)。

    n=1 で 1.0(効果なし)。nが増えるほど `1 + ACCESSIBILITY_GAIN_MAX` に漸近する
    飽和カーブ。無限に効果が増え続けることはない(上限あり)。
    """
    if num_performances <= 1:
        return 1.0
    return 1 + c2.ACCESSIBILITY_GAIN_MAX * (1 - num_performances ** (-c2.ACCESSIBILITY_GAIN_DECAY))


def cannibalization_multiplier(num_performances: int) -> float:
    """公演回数nに対するCannibalization乗数(区分: structural、v0.1のPOOL_EXPONENTと同値)。"""
    return num_performances**c2.CANNIBALIZATION_EXPONENT_V2


class RuleBasedDemandEstimatorV2(DemandEstimator):
    """rule_v0.2のMVP実装。v0.1を内部コンポーネントとして再利用する。"""

    def __init__(self) -> None:
        self._v1 = RuleBasedDemandEstimator()

    def estimate_demand(self, features: DemandFeatures) -> DemandEstimate:
        v1_estimate = self._v1.estimate_demand(features)
        n = features.num_performances

        accessibility = accessibility_gain(n)
        cannibalization = cannibalization_multiplier(n)
        total_expected_demand = (
            v1_estimate.expected_demand_per_performance * accessibility * cannibalization
        )

        explanation: list[ExplanationItem] = list(v1_estimate.explanation)
        if n > 1:
            explanation.append(
                ExplanationItem(
                    factor="accessibility_gain_v2",
                    multiplier=accessibility,
                    description=(
                        f"公演回数{n}回による日程アクセシビリティ向上(heuristic, "
                        f"上限+{c2.ACCESSIBILITY_GAIN_MAX * 100:.0f}%): 需要"
                        f"{(accessibility - 1) * 100:+.1f}%"
                    ),
                )
            )
            explanation.append(
                ExplanationItem(
                    factor="cannibalization_v2",
                    multiplier=cannibalization / n,
                    description=(
                        f"公演回数{n}回の観客プール逓減(cannibalization, "
                        f"指数{c2.CANNIBALIZATION_EXPONENT_V2}はv0.1のPOOL_EXPONENTを継承)"
                    ),
                )
            )

        return DemandEstimate(
            base_attendance_power=v1_estimate.base_attendance_power,
            baseline_price=v1_estimate.baseline_price,
            expected_demand_per_performance=v1_estimate.expected_demand_per_performance,
            total_expected_demand=total_expected_demand,
            explanation=explanation,
        )
