"""rule_v0.1 と rule_v0.2 を同一の実在benchmark datasetでHistorical Backtestし、
比較結果を docs/RULE_V0_2_EVALUATION.md と benchmarks/results/ 配下のCSVへ出力する。

使い方:
    backend/.venv/Scripts/python.exe -m benchmarks.scripts.compare_model_versions

重要:
- rule_v0.1(backend/app/calculation/constants.py 他)は一切変更しない。
- 「実売価格に近づいたから良い」という評価は行わない(README/RULE_V0_2_EVALUATION.md参照)。
- is_synthetic=true の行は実在団体の評価とは明確に分離して報告する。
"""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

from benchmarks.scripts import _bootstrap  # noqa: F401
from benchmarks.scripts.backtest import build_backtest_pairs, split_standard_and_special_condition_cases
from benchmarks.scripts.dataset_io import DEFAULT_DATASET_PATH, load_dataset
from benchmarks.scripts.metrics import RESULT_CSV_COLUMNS, BenchmarkResult, evaluate_pair
from benchmarks.scripts.model_registry import get_model_entry

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"


def _write_csv(results: list[BenchmarkResult], path: Path) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_CSV_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_row())


def _fmt(v, digits: int = 1) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def run_comparison(dataset_path: Path = DEFAULT_DATASET_PATH) -> dict[str, list[BenchmarkResult]]:
    dataset = load_dataset(dataset_path)
    standard_cases, _special = split_standard_and_special_condition_cases(dataset.valid_cases)
    pairs = build_backtest_pairs(standard_cases)

    synthetic_ids = {c.benchmark_id for c in dataset.valid_cases if c.is_synthetic}

    all_results: dict[str, list[BenchmarkResult]] = {}
    for key in ("rule_v0.1", "rule_v0.2"):
        entry = get_model_entry(key)
        results = [
            evaluate_pair(pair, estimator=entry.estimator_factory(), model_version=entry.model_version)
            for pair in pairs
        ]
        all_results[key] = results
        csv_path = RESULTS_DIR / f"benchmark_results_{key.replace('.', '_').replace('-', '_')}.csv"
        _write_csv(results, csv_path)
        print(f"[compare_model_versions] wrote {len(results)} rows -> {csv_path}")

    write_evaluation_report(all_results["rule_v0.1"], all_results["rule_v0.2"], synthetic_ids)
    return all_results


def _index_by_id(results: list[BenchmarkResult]) -> dict[str, BenchmarkResult]:
    return {r.benchmark_id: r for r in results}


def write_evaluation_report(
    results_v1: list[BenchmarkResult],
    results_v2: list[BenchmarkResult],
    synthetic_ids: set[str],
) -> Path:
    v1_by_id = _index_by_id(results_v1)
    v2_by_id = _index_by_id(results_v2)

    lines: list[str] = []
    lines.append("# RULE_V0_2_EVALUATION.md")
    lines.append("")
    lines.append(
        "rule_v0.1 と rule_v0.2 を同一の実在benchmark dataset(`benchmarks/data/"
        "public_performances.csv`)でHistorical Backtestし比較した結果。"
    )
    lines.append("")
    lines.append("## 評価原則(重要)")
    lines.append("")
    lines.append(
        "**「実売価格(actual_ticket_price)に近づいたからv0.2が優れている」とは評価しない。**"
        "実売価格は最適価格の正解ラベルではない。優先順位は以下の通り:"
    )
    lines.append("")
    lines.append("1. 公開された事実(全公演完売等)と矛盾しないか(demand_coverage_ratio)")
    lines.append("2. 既存Invariantを壊していないか")
    lines.append("3. Cold Start(履歴が薄い場合)で極端な推奨を無警告で出さないか")
    lines.append("4. 価格推奨の安定性")
    lines.append("5. 実価格との差は参考指標に過ぎない(最下位の優先度)")
    lines.append("")

    real_ids = sorted(set(v1_by_id) & set(v2_by_id) - synthetic_ids)
    synthetic_ids_present = sorted((set(v1_by_id) & set(v2_by_id)) & synthetic_ids)

    lines.append("## 実在データでの比較(評価済みtargetのみ)")
    lines.append("")
    evaluated_real_ids = [i for i in real_ids if v1_by_id[i].status == "evaluated"]
    if evaluated_real_ids:
        lines.append(
            "| benchmark_id | 団体 | actual price | balanced v0.1 | balanced v0.2 | "
            "gap% v0.1 | gap% v0.2 | total demand v0.1 | total demand v0.2 | "
            "coverage v0.1 | coverage v0.2 | violation v0.1/v0.2 | Venue Fit v0.1/v0.2 | "
            "boundary_hit v0.1/v0.2 | usable_history |"
        )
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|")
        for bid in evaluated_real_ids:
            r1, r2 = v1_by_id[bid], v2_by_id[bid]
            lines.append(
                f"| {bid} | {r1.organization_name} | {_fmt(r1.actual_ticket_price, 0)}円 | "
                f"{_fmt(r1.balanced_price, 0)}円 | {_fmt(r2.balanced_price, 0)}円 | "
                f"{_fmt(r1.percentage_price_gap)}% | {_fmt(r2.percentage_price_gap)}% | "
                f"{_fmt(r1.predicted_demand_at_actual_price)} | "
                f"{_fmt(r2.predicted_demand_at_actual_price)} | "
                f"{_fmt(r1.demand_coverage_ratio, 3)} | {_fmt(r2.demand_coverage_ratio, 3)} | "
                f"{r1.sold_out_lower_bound_violation}/{r2.sold_out_lower_bound_violation} | "
                f"{r1.venue_fit_at_actual_price}/{r2.venue_fit_at_actual_price} | "
                f"{r1.price_search_boundary_hit}/{r2.price_search_boundary_hit} | "
                f"{r1.num_history_performances} |"
            )
    else:
        lines.append("評価済みの実在target数が0件のためN/A。")
    lines.append("")

    lines.append("## 合成データ(is_synthetic=true)での比較 — 参考情報")
    lines.append("")
    lines.append("実在団体の評価には一切含めていない、動作確認用の架空データの比較。")
    lines.append("")
    if synthetic_ids_present:
        for bid in synthetic_ids_present:
            r1, r2 = v1_by_id[bid], v2_by_id[bid]
            if r1.status != "evaluated":
                lines.append(f"- {bid}: skipped ({r1.skip_reason})")
                continue
            lines.append(
                f"- {bid}: balanced v0.1={_fmt(r1.balanced_price, 0)}円 / "
                f"v0.2={_fmt(r2.balanced_price, 0)}円, "
                f"coverage v0.1={_fmt(r1.demand_coverage_ratio, 3)} / "
                f"v0.2={_fmt(r2.demand_coverage_ratio, 3)}"
            )
    else:
        lines.append("該当なし。")
    lines.append("")

    # --- Cold Start比較(usable_history_count別) ---
    lines.append("## Cold Start比較(usable_history_count別)")
    lines.append("")
    lines.append(
        "| usable_history_count | 件数 | boundary_hit率 v0.1 | boundary_hit率 v0.2 | "
        "data_sufficiency | strong_recommendation_allowed |"
    )
    lines.append("|---:|---:|---:|---:|---|---|")
    for k in (1, 2, 3, 4):
        ids_k = [
            bid for bid in evaluated_real_ids
            if v1_by_id[bid].num_history_performances == (k if k < 4 else v1_by_id[bid].num_history_performances)
            and (v1_by_id[bid].num_history_performances == k or (k == 4 and v1_by_id[bid].num_history_performances >= 4))
        ]
        if not ids_k:
            lines.append(f"| {k}{'+' if k == 4 else ''} | 0 | N/A | N/A | N/A | N/A |")
            continue
        b1 = sum(1 for bid in ids_k if v1_by_id[bid].price_search_boundary_hit) / len(ids_k)
        b2 = sum(1 for bid in ids_k if v2_by_id[bid].price_search_boundary_hit) / len(ids_k)
        suff = v1_by_id[ids_k[0]].data_sufficiency
        allowed = v1_by_id[ids_k[0]].is_strong_recommendation_allowed
        lines.append(
            f"| {k}{'+' if k == 4 else ''} | {len(ids_k)} | {b1 * 100:.0f}% | {b2 * 100:.0f}% | "
            f"{suff} | {allowed} |"
        )
    lines.append("")
    lines.append(
        "`data_sufficiency`/`is_strong_recommendation_allowed`はusable_history_countのみに"
        "依存するため、v0.1・v0.2で共通の値になる(Recommender自体は変更していないため)。"
    )
    lines.append("")

    # --- Multi-performance比較(performance_countバケット別) ---
    lines.append("## Multi-performance比較(performance_countバケット別)")
    lines.append("")
    from benchmarks.scripts.diagnostics import bucket_performance_count

    buckets = ["5-8", "9-15", "16-20", "21+"]
    lines.append(
        "| bucket | 件数 | coverage v0.1(平均) | coverage v0.2(平均) | "
        "violation率 v0.1 | violation率 v0.2 |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    for b in buckets:
        ids_b = [
            bid for bid in evaluated_real_ids
            if bucket_performance_count(v1_by_id[bid].performance_count) == b
        ]
        if not ids_b:
            lines.append(f"| {b} | 0 | N/A | N/A | N/A | N/A |")
            continue
        cov1 = [r.demand_coverage_ratio for r in (v1_by_id[bid] for bid in ids_b)
                if r.demand_coverage_ratio is not None]
        cov2 = [r.demand_coverage_ratio for r in (v2_by_id[bid] for bid in ids_b)
                if r.demand_coverage_ratio is not None]
        viol1 = [
            bool(v1_by_id[bid].sold_out_lower_bound_violation) for bid in ids_b
            if v1_by_id[bid].sold_out_lower_bound_violation is not None
        ]
        viol2 = [
            bool(v2_by_id[bid].sold_out_lower_bound_violation) for bid in ids_b
            if v2_by_id[bid].sold_out_lower_bound_violation is not None
        ]
        cov1_str = _fmt(statistics.mean(cov1), 3) if cov1 else "N/A"
        cov2_str = _fmt(statistics.mean(cov2), 3) if cov2 else "N/A"
        viol1_str = f"{sum(viol1) / len(viol1) * 100:.0f}%" if viol1 else "N/A"
        viol2_str = f"{sum(viol2) / len(viol2) * 100:.0f}%" if viol2 else "N/A"
        lines.append(f"| {b} | {len(ids_b)} | {cov1_str} | {cov2_str} | {viol1_str} | {viol2_str} |")
    lines.append("")

    lines.append("## データ品質に関する注意")
    lines.append("")
    lines.append(
        "- モデル係数(rule_v0.1)は本比較のために一切変更していない。"
        "rule_v0.2はrule_v0.1のestimate_demand()を内部で再利用しており、n=1では両者は完全に一致する。"
    )
    evaluated_org_count = len({v1_by_id[bid].organization_name for bid in evaluated_real_ids})
    lines.append(
        f"- サンプル数が非常に少ないため(実在団体{evaluated_org_count}団体、"
        f"評価済みtarget数{len(evaluated_real_ids)}件)、"
        "本比較は「確定的な優劣判定」ではなく「観測された傾向」として扱うこと。"
    )
    lines.append("")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_DIR / "RULE_V0_2_EVALUATION.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    run_comparison()
