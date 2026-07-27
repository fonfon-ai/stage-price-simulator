"""Sensitivity Analysis: 主要パラメータを±10%/±20%変化させ、
推奨価格・予想需要・推奨Venue Fit・売上・利益への影響を計測する。

docs/CALIBRATION_REPORT.md のSensitivity Analysis節の元データを生成するための
使い捨てスクリプト(pytestテストではなく、レポート作成用の分析ツール)。

実行方法:
    cd backend
    .venv/Scripts/python.exe scripts/sensitivity_analysis.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.calculation import constants as c  # noqa: E402
from app.calculation.demand_estimator import RuleBasedDemandEstimator  # noqa: E402
from app.calculation.recommender import recommend, run_full_search  # noqa: E402
from app.calculation.simulator import PerformanceSimulator  # noqa: E402
from app.calculation.types import (  # noqa: E402
    CurrentProductionInput,
    DemandFeatures,
    Genre,
    GroupInfo,
    PastPerformance,
    RarityLevel,
    VenueCandidate,
)

# --- 代表シナリオ(中規模団体・適正会場) ---
GROUP = GroupInfo(
    name="サンプル団体",
    genre=Genre.PLAY,
    years_active=5,
    sns_x_followers=3000,
    sns_instagram_followers=1500,
    sns_youtube_subscribers=500,
    sns_other_followers=0,
)
PAST = [
    PastPerformance(
        name="公演A",
        performance_date=dt.date(2026, 4, 1),
        capacity=200,
        price=3500,
        num_performances=1,
        tickets_sold=180,
        sold_out=True,
        days_before_sold_out=5,
        is_new_work=True,
        is_weekend_holiday=True,
        is_evening=False,
    ),
    PastPerformance(
        name="公演B",
        performance_date=dt.date(2026, 1, 1),
        capacity=150,
        price=3300,
        num_performances=1,
        tickets_sold=120,
        sold_out=False,
        is_new_work=False,
        is_weekend_holiday=False,
        is_evening=False,
    ),
]
CURRENT = CurrentProductionInput(
    area="東京都",
    is_new_work=True,
    is_weekend_holiday=True,
    is_evening=False,
    rarity_level=RarityLevel.MID,
    has_guest=False,
    is_special=False,
    price_min=2500,
    price_max=5500,
)
VENUE = VenueCandidate(
    name="会場X", area="東京都", capacity=220, venue_cost=250000,
    walk_minutes=5, location_rating=3, brand_rating=3,
)


def _run_pipeline():
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)
    features = DemandFeatures(
        group=GROUP, past_performances=PAST, current_production=CURRENT,
        venue=VENUE, price=CURRENT.price_min, num_performances=1,
    )
    reference = estimator.estimate_demand(features)
    scenarios = run_full_search(
        simulator, features, [VENUE], [1], CURRENT.price_min, CURRENT.price_max
    )
    rec = recommend(scenarios, reference.baseline_price)
    return {
        "balance_price": rec.balance_price,
        "balance_demand": rec.balance_scenario.expected_demand,
        "balance_occupancy": rec.balance_scenario.occupancy_rate,
        "balance_venue_fit": rec.balance_scenario.venue_fit.value,
        "balance_revenue": rec.balance_scenario.revenue,
        "balance_profit": rec.balance_scenario.profit,
    }


PARAMS_TO_TEST = [
    "ATTENDANCE_DECAY",
    "SOLD_OUT_BASE_CORRECTION",
    "SOLD_OUT_EARLY_BONUS_PER_DAY",
    "PRICE_ELASTICITY",
    "WEEKEND_HOLIDAY_FACTOR",
    "EVENING_FACTOR",
    "NEW_WORK_FACTOR",
    "GUEST_FACTOR",
    "SPECIAL_FACTOR",
    "LOCATION_RATING_STEP",
    "BRAND_RATING_STEP",
    "SNS_FACTOR_SCALE",
    "SNS_FACTOR_CAP",
    "POOL_EXPONENT",
    "BALANCE_WEIGHT_OCCUPANCY",
    "BALANCE_WEIGHT_REVENUE",
    "BALANCE_WEIGHT_PROFIT",
    "BALANCE_WEIGHT_DISCOUNT_PENALTY",
]


def main():
    baseline = _run_pipeline()
    results = {"baseline": baseline, "sensitivity": {}}

    for param in PARAMS_TO_TEST:
        original = getattr(c, param)
        param_results = {}
        for pct in (-0.20, -0.10, 0.10, 0.20):
            setattr(c, param, original * (1 + pct))
            try:
                out = _run_pipeline()
            finally:
                setattr(c, param, original)
            price_change_pct = (
                (out["balance_price"] - baseline["balance_price"]) / baseline["balance_price"] * 100
            )
            demand_change_pct = (
                (out["balance_demand"] - baseline["balance_demand"])
                / baseline["balance_demand"]
                * 100
                if baseline["balance_demand"]
                else 0.0
            )
            revenue_change_pct = (
                (out["balance_revenue"] - baseline["balance_revenue"])
                / baseline["balance_revenue"]
                * 100
                if baseline["balance_revenue"]
                else 0.0
            )
            profit_change_pct = (
                (out["balance_profit"] - baseline["balance_profit"])
                / abs(baseline["balance_profit"])
                * 100
                if baseline["balance_profit"]
                else 0.0
            )
            param_results[f"{pct:+.0%}"] = {
                "balance_price": out["balance_price"],
                "price_change_pct": round(price_change_pct, 2),
                "demand_change_pct": round(demand_change_pct, 2),
                "revenue_change_pct": round(revenue_change_pct, 2),
                "profit_change_pct": round(profit_change_pct, 2),
                "venue_fit_changed": out["balance_venue_fit"] != baseline["balance_venue_fit"],
                "venue_fit": out["balance_venue_fit"],
            }
        results["sensitivity"][param] = param_results

    print(json.dumps(results, ensure_ascii=False, indent=2))

    # high sensitivity判定: ±10%変化で価格が±5%以上動く場合
    print("\n--- HIGH SENSITIVITY PARAMS (±10%入力 -> 価格±5%以上変化) ---", file=sys.stderr)
    for param, param_results in results["sensitivity"].items():
        for pct_label in ("-10%", "+10%"):
            change = param_results[pct_label]["price_change_pct"]
            if abs(change) >= 5.0:
                print(f"{param} {pct_label}: price_change={change}%", file=sys.stderr)


if __name__ == "__main__":
    main()
