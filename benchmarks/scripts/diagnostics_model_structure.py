"""Model Structure Diagnostic (read-only).

docs/MODEL_STRUCTURE_DIAGNOSTIC.md の元データを生成するための使い捨て診断スクリプト。

重要: rule_v0.1・27係数は一切恒久変更しない。POOL_EXPONENTのwhat-if診断は
constants.POOL_EXPONENT を一時的にモンキーパッチし、各シナリオ計算後に必ず元の値へ
復元する(sensitivity_analysis.py と同じパターン)。本スクリプト自体もconstants.pyや
DemandEstimator/PerformanceSimulator/Recommenderのコードを一切変更しない。

実行方法:
    cd (repo root)
    backend/.venv/Scripts/python.exe -m benchmarks.scripts.diagnostics_model_structure
"""
from __future__ import annotations

import datetime as dt
import json

from benchmarks.scripts import _bootstrap  # noqa: F401
from benchmarks.scripts.backtest import build_backtest_pairs
from benchmarks.scripts.dataset_io import load_dataset
from benchmarks.scripts.model_adapter import build_past_performances, build_target_features

from app.calculation import constants as c  # noqa: E402
from app.calculation.demand_estimator import RuleBasedDemandEstimator  # noqa: E402
from app.calculation.recommender import _occupancy_closeness, _normalize, recommend, run_full_search  # noqa: E402
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


# ============================================================
# Theme 1: Multi-performance Demand Scaling
# ============================================================

def theme1_multi_performance_scaling():
    print("\n=== THEME 1: Multi-performance Demand Scaling (POOL_EXPONENT) ===")
    print(f"POOL_EXPONENT (current, unchanged) = {c.POOL_EXPONENT}")

    # 本多劇場(386席)で1公演あたり満席(386人)が続いていると仮定した、
    # 制御されたbase_attendance_powerを使う(実データのシソンヌ2019相当)。
    group = GroupInfo(name="診断用団体", genre=Genre.CONTE, years_active=10)
    past = [
        PastPerformance(
            name="診断用過去公演",
            performance_date=dt.date(2019, 1, 1),
            capacity=386,
            price=5000,
            num_performances=14,
            tickets_sold=386 * 14,
            sold_out=True,
            is_new_work=False,
            is_weekend_holiday=False,
            is_evening=False,
        )
    ]
    current_production = CurrentProductionInput(
        area="東京都", is_new_work=False, is_weekend_holiday=False, is_evening=False,
        rarity_level=RarityLevel.LOW, has_guest=False, is_special=False,
        price_min=5000, price_max=5000,
    )
    venue = VenueCandidate(
        name="本多劇場相当", area="東京都", capacity=386, venue_cost=0,
        walk_minutes=5, location_rating=3, brand_rating=3,
    )
    estimator = RuleBasedDemandEstimator()

    counts = [1, 2, 5, 10, 14, 16, 21, 22]
    rows = []
    for n in counts:
        features = DemandFeatures(
            group=group, past_performances=past, current_production=current_production,
            venue=venue, price=5000, num_performances=n,
        )
        estimate = estimator.estimate_demand(features)
        per_perf = estimate.total_expected_demand / n
        rows.append({
            "num_performances": n,
            "pool_multiplier_n_pow_exponent": n ** c.POOL_EXPONENT,
            "total_expected_demand": estimate.total_expected_demand,
            "demand_per_performance": per_perf,
            "required_capacity_total_if_full_sellout": 386 * n,
            "coverage_ratio_vs_full_sellout": estimate.total_expected_demand / (386 * n),
        })
        print(
            f"n={n:>3}  pool_mult(n^{c.POOL_EXPONENT})={n ** c.POOL_EXPONENT:8.3f}  "
            f"total_demand={estimate.total_expected_demand:10.2f}  "
            f"per_perf={per_perf:8.3f}  "
            f"full_sellout_seats={386*n:6d}  "
            f"coverage={estimate.total_expected_demand/(386*n)*100:6.2f}%"
        )

    ratio_1_to_22 = rows[-1]["total_expected_demand"] / rows[0]["total_expected_demand"]
    print(f"\n1公演->22公演の総需要倍率: {ratio_1_to_22:.3f}倍 (単純線形なら22倍のはず)")
    print(f"理論上の n^POOL_EXPONENT 比 (22^{c.POOL_EXPONENT} / 1^{c.POOL_EXPONENT}) = {22 ** c.POOL_EXPONENT:.3f}")
    return rows


# ============================================================
# Theme 2: Thin History / Cold Start
# ============================================================

def _real_sissonne_features_for(target_id: str):
    dataset = load_dataset()
    pairs = build_backtest_pairs(
        [c_ for c_ in dataset.valid_cases if not c_.excluded_from_standard_backtest]
    )
    pair = next(p for p in pairs if p.target.benchmark_id == target_id)
    history_conv = build_past_performances(pair.history)
    target_conv = build_target_features(pair.target, history_conv.past_performances)
    return pair, history_conv, target_conv


def theme2_thin_history():
    print("\n=== THEME 2: Thin History / Cold Start (REAL-0005, 2022) ===")
    pair, history_conv, target_conv = _real_sissonne_features_for("REAL-0005")
    features = target_conv.features
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)

    reference = estimator.estimate_demand(features)
    print(f"history件数: {len(history_conv.past_performances)}")
    print(f"base_attendance_power (1公演あたり): {reference.base_attendance_power:.2f}")
    print(f"baseline_price (過去加重平均価格): {reference.baseline_price:.2f}")
    print(f"price_search_range: {target_conv.price_min} - {target_conv.price_max}")
    for e in reference.explanation:
        print(f"  explanation: {e.factor} x{e.multiplier:.4f} - {e.description}")

    scenarios = run_full_search(
        simulator, features, [features.venue], [features.num_performances],
        target_conv.price_min, target_conv.price_max,
    )
    rec = recommend(scenarios, reference.baseline_price)
    print(f"\nbalanced_price = {rec.balance_price} (探索レンジ上限={target_conv.price_max})")

    occ = [_occupancy_closeness(s.occupancy_rate) for s in scenarios]
    rev_norm = _normalize([s.revenue for s in scenarios])
    prof_norm = _normalize([s.profit for s in scenarios])
    print("\nprice | occupancy_rate | occ_closeness | revenue_norm | profit_norm")
    for s, o, rv, pf in zip(scenarios, occ, rev_norm, prof_norm):
        print(f"  {s.price:6d} | {s.occupancy_rate*100:6.2f}% | {o:.3f} | {rv:.3f} | {pf:.3f}")

    # --- controlled synthetic diagnostic: 履歴件数を1->4に変えた場合の推奨価格の安定性 ---
    print("\n--- Synthetic diagnostic: 同一target条件でhistory件数のみ変化 ---")
    group = GroupInfo(name="診断用シソンヌ相当", genre=Genre.CONTE, years_active=10)
    synthetic_history_full = [
        PastPerformance(
            name="H2019", performance_date=dt.date(2019, 1, 1), capacity=386, price=5000,
            num_performances=14, tickets_sold=386 * 14, sold_out=True,
            is_new_work=False, is_weekend_holiday=False, is_evening=False,
        ),
        PastPerformance(
            name="H2022", performance_date=dt.date(2022, 1, 1), capacity=386, price=8000,
            num_performances=16, tickets_sold=386 * 16, sold_out=True,
            is_new_work=False, is_weekend_holiday=False, is_evening=False,
        ),
        PastPerformance(
            name="H2023", performance_date=dt.date(2023, 1, 1), capacity=386, price=8000,
            num_performances=21, tickets_sold=386 * 21, sold_out=True,
            is_new_work=False, is_weekend_holiday=False, is_evening=False,
        ),
        PastPerformance(
            name="H2024", performance_date=dt.date(2024, 1, 1), capacity=386, price=8000,
            num_performances=21, tickets_sold=386 * 21, sold_out=True,
            is_new_work=False, is_weekend_holiday=False, is_evening=False,
        ),
    ]
    current_production = CurrentProductionInput(
        area="東京都", is_new_work=False, is_weekend_holiday=False, is_evening=False,
        rarity_level=RarityLevel.LOW, has_guest=False, is_special=False,
        price_min=4000, price_max=14400,
    )
    venue = VenueCandidate(
        name="本多劇場相当", area="東京都", capacity=386, venue_cost=0,
        walk_minutes=5, location_rating=3, brand_rating=3,
    )
    for k in (1, 2, 3, 4):
        hist_k = synthetic_history_full[:k]
        feat = DemandFeatures(
            group=group, past_performances=hist_k, current_production=current_production,
            venue=venue, price=8000, num_performances=22,
        )
        ref_k = estimator.estimate_demand(feat)
        scen_k = run_full_search(simulator, feat, [venue], [22], 4000, 14400)
        rec_k = recommend(scen_k, ref_k.baseline_price)
        print(
            f"history={k}件  base_attendance_power={ref_k.base_attendance_power:8.2f}  "
            f"baseline_price={ref_k.baseline_price:8.2f}  balanced_price={rec_k.balance_price:6d}  "
            f"gap_vs_actual(8000)={(rec_k.balance_price-8000)/8000*100:+6.2f}%"
        )


# ============================================================
# Theme 3: Recommendation Objective decomposition
# ============================================================

def theme3_recommendation_objective():
    print("\n=== THEME 3: Recommendation Objective decomposition (REAL-0006/0007/0008) ===")
    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)
    for target_id in ("REAL-0006", "REAL-0007", "REAL-0008"):
        pair, history_conv, target_conv = _real_sissonne_features_for(target_id)
        features = target_conv.features
        reference = estimator.estimate_demand(features)
        scenarios = run_full_search(
            simulator, features, [features.venue], [features.num_performances],
            target_conv.price_min, target_conv.price_max,
        )
        rec = recommend(scenarios, reference.baseline_price)
        occ = [_occupancy_closeness(s.occupancy_rate) for s in scenarios]
        rev_norm = _normalize([s.revenue for s in scenarios])
        prof_norm = _normalize([s.profit for s in scenarios])
        print(f"\n--- {target_id} (actual=8000) ---")
        print(f"balanced_price={rec.balance_price}  revenue_price={rec.revenue_price}  profit_price={rec.profit_price}")
        for s, o, rv, pf in zip(scenarios, occ, rev_norm, prof_norm):
            score = (
                c.BALANCE_WEIGHT_OCCUPANCY * o
                + c.BALANCE_WEIGHT_REVENUE * rv
                + c.BALANCE_WEIGHT_PROFIT * pf
            )
            marker = " <== balanced" if s.price == rec.balance_price else ""
            print(
                f"  price={s.price:6d} occ%={s.occupancy_rate*100:6.2f} occ_close={o:.3f} "
                f"rev_norm={rv:.3f} prof_norm={pf:.3f} score={score:.4f}{marker}"
            )


# ============================================================
# Sensitivity Diagnostic: POOL_EXPONENT what-if (temporary monkeypatch only)
# ============================================================

def sensitivity_pool_exponent():
    print("\n=== SENSITIVITY DIAGNOSTIC: POOL_EXPONENT what-if (rule_v0.1は変更しない) ===")
    original = c.POOL_EXPONENT
    values = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]
    results = {}
    try:
        for target_id in ("REAL-0006", "REAL-0007", "REAL-0008"):
            results[target_id] = []
            for v in values:
                c.POOL_EXPONENT = v
                estimator = RuleBasedDemandEstimator()
                simulator = PerformanceSimulator(estimator)
                pair, history_conv, target_conv = _real_sissonne_features_for(target_id)
                features = target_conv.features
                reference = estimator.estimate_demand(features)
                scenarios = run_full_search(
                    simulator, features, [features.venue], [features.num_performances],
                    target_conv.price_min, target_conv.price_max,
                )
                rec = recommend(scenarios, reference.baseline_price)
                actual_scenario = simulator.simulate(
                    features, features.venue, 8000, features.num_performances
                )
                violation = actual_scenario.expected_demand < actual_scenario.available_seats
                row = {
                    "pool_exponent": v,
                    "predicted_total_demand": actual_scenario.expected_demand,
                    "predicted_demand_per_performance": (
                        actual_scenario.expected_demand / features.num_performances
                    ),
                    "sold_out_lower_bound_violation": violation,
                    "venue_fit": actual_scenario.venue_fit.value,
                    "balanced_price": rec.balance_price,
                }
                results[target_id].append(row)
                print(
                    f"{target_id} POOL_EXPONENT={v:.2f}  total_demand={row['predicted_total_demand']:9.2f}  "
                    f"per_perf={row['predicted_demand_per_performance']:7.2f}  "
                    f"violation={row['sold_out_lower_bound_violation']}  "
                    f"venue_fit={row['venue_fit']:14s}  balanced={row['balanced_price']}"
                )
    finally:
        c.POOL_EXPONENT = original
        assert c.POOL_EXPONENT == original
    print(f"\n(復元確認) POOL_EXPONENT = {c.POOL_EXPONENT} (元の値に復元済み)")
    return results


def main():
    theme1_rows = theme1_multi_performance_scaling()
    theme2_thin_history()
    theme3_recommendation_objective()
    sensitivity_results = sensitivity_pool_exponent()

    print("\n=== JSON DUMP (for report authoring) ===")
    print(json.dumps({
        "theme1": theme1_rows,
        "sensitivity": sensitivity_results,
    }, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
