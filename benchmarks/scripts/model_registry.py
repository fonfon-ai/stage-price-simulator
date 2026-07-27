"""利用可能なモデルバージョンのレジストリ(config/strategyパターン)。

rule_v0.1・rule_v0.2それぞれのDemandEstimator実装とモデルバージョン文字列を
一箇所で管理する。新しいモデルバージョンを追加する場合はここにエントリを足すだけでよく、
Benchmark実行スクリプト側のロジックは変更不要。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.calculation import constants as calc_constants
from app.calculation import constants_v2 as calc_constants_v2
from app.calculation.demand_estimator import DemandEstimator, RuleBasedDemandEstimator
from app.calculation.demand_estimator_v2 import RuleBasedDemandEstimatorV2


@dataclass(frozen=True)
class ModelVersionEntry:
    model_version: str
    estimator_factory: Callable[[], DemandEstimator]


MODEL_REGISTRY: dict[str, ModelVersionEntry] = {
    "rule_v0.1": ModelVersionEntry(
        model_version=calc_constants.MODEL_VERSION,
        estimator_factory=RuleBasedDemandEstimator,
    ),
    "rule_v0.2": ModelVersionEntry(
        model_version=calc_constants_v2.MODEL_VERSION_V2,
        estimator_factory=RuleBasedDemandEstimatorV2,
    ),
}


def get_model_entry(key: str) -> ModelVersionEntry:
    if key not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model version key: {key!r}. Known keys: {list(MODEL_REGISTRY)}")
    return MODEL_REGISTRY[key]
