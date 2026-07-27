"""Venue Fit 判定。テンプレートベースで文言を生成する（LLM不使用）。"""
from __future__ import annotations

from app.calculation import constants as c
from app.calculation.types import VenueFitCategory


def classify_venue_fit(occupancy_rate: float) -> tuple[VenueFitCategory, str]:
    if occupancy_rate >= c.VENUE_FIT_TOO_SMALL_THRESHOLD:
        return (
            VenueFitCategory.TOO_SMALL,
            f"予想稼働率が{occupancy_rate * 100:.0f}%となり、現在の集客実績に対して"
            "この会場は小さすぎる可能性があります。より大きな会場も検討できます。",
        )
    if occupancy_rate >= c.VENUE_FIT_GOOD_MIN:
        return (
            VenueFitCategory.GOOD,
            f"予想稼働率は{occupancy_rate * 100:.0f}%で、現在の集客実績に対して適切な規模です。",
        )
    if occupancy_rate >= c.VENUE_FIT_SLIGHTLY_LARGE_MIN:
        return (
            VenueFitCategory.SLIGHTLY_LARGE,
            f"予想稼働率は{occupancy_rate * 100:.0f}%となり、現在の集客実績に対して"
            "やや大型です。空席リスクに注意してください。",
        )
    return (
        VenueFitCategory.TOO_LARGE,
        f"この会場では予想稼働率が{occupancy_rate * 100:.0f}%となり、"
        "現在の集客実績に対して大きすぎる可能性があります。空席リスクが高い設計です。",
    )
