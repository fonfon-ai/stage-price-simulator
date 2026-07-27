"""現在のモデル係数(constants.py)をversion付きでスナップショット化するユーティリティ。

係数そのものは一切変更しない。既存の27係数 + MODEL_VERSION を dict として書き出すだけの
薄いラッパーであり、External Benchmark実行時に「どのバージョンの係数で計算したか」を
再現・記録できるようにするためのものである。
"""
from __future__ import annotations

from app.calculation import constants as c


def snapshot() -> dict:
    """constants.py 内の全定数を dict として返す(private/呼び出し可能オブジェクトは除外)。"""
    return {
        name: getattr(c, name)
        for name in dir(c)
        if not name.startswith("_") and not callable(getattr(c, name))
    }


def model_version() -> str:
    return c.MODEL_VERSION
