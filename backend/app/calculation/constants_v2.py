"""[EXPERIMENTAL] rule_v0.2で新規追加する定数のみを定義する。Production defaultではない
(現在の判定: NOT ENOUGH DATA。docs/RULE_V0_2_EVALUATION.md参照)。

rule_v0.1(`constants.py`)の27係数は一切変更・複製しない。v0.2の需要推定は
内部でv0.1の`RuleBasedDemandEstimator`をそのまま呼び出し、公演回数→興行全体需要への
変換ステップだけをここで定義する2つの新係数(Accessibility Gain)で置き換える。

各係数には根拠区分を明記する:
  - empirical:        実データから統計的に推定された値
  - heuristic:         最小限の仮定として置いた初期値。実証データ不足のため今後の
                       再キャリブレーション対象。
  - structural:        値そのものよりも「この構造(関数形)を導入すること」自体が
                       設計判断であるもの。

詳細な設計根拠は docs/RULE_V0_2_DESIGN.md を参照。
"""
from __future__ import annotations

# rule_v0.1のPOOL_EXPONENTをそのまま参照する(値の二重管理を避けるため)。
from app.calculation.constants import POOL_EXPONENT as CANNIBALIZATION_EXPONENT_V2  # noqa: F401

MODEL_VERSION_V2 = "rule_v0.2"

# --- Multi-performance Demand Scaling: Accessibility × Cannibalization ---

# Cannibalization: 同一runの複数公演が観客プールを共有する度合い。
# 区分: structural — 「値を変えて数字を合わせる」ことを避けるため、実証データが
# 無い現時点では意図的にv0.1(POOL_EXPONENT)と同一値を維持する
# (上のimportで再エクスポートしている。定義自体はconstants.pyにあり、ここでの
# 再定義・再チューニングは行わない)。

# Accessibility Gain: 公演回数が増えるほど「その日程なら行ける」観客が増える効果。
# ACCESSIBILITY_GAIN_MAX: 生涯到達可能な追加需要の上限(区分: heuristic)。
#   「公演回数を無限に増やしても、日程の融通による追加需要は+30%程度で頭打ちになる」
#   という保守的な仮定。実データによる裏付けはまだ無く、今後シソンヌ以外の団体データが
#   蓄積された時点で再キャリブレーションが必要。
ACCESSIBILITY_GAIN_MAX = 0.30

# ACCESSIBILITY_GAIN_DECAY: 追加需要が頭打ちに近づく速さ(区分: heuristic)。
#   n=1で0(効果なし)、nが増えるほど1に近づく飽和カーブの減衰率。0.5は
#   「公演数が2〜3回に増えた時点である程度効果が立ち上がり、10回を超えると
#   ほぼ頭打ちになる」という穏やかな飽和を意図した初期値であり、これも
#   実証データに基づくものではない。
ACCESSIBILITY_GAIN_DECAY = 0.5
