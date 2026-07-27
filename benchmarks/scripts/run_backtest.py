"""External Benchmark / Historical Backtest 実行エントリポイント。

使い方:
    python -m benchmarks.scripts.run_backtest
    python -m benchmarks.scripts.run_backtest --dataset path/to/other.csv

既存モデル(RuleBasedDemandEstimator / PerformanceSimulator / Recommender)をそのまま呼び出し、
benchmarks/data/*.csv のデータに対して Historical Backtest を実行する。
モデル係数(rule_v0.1)は一切変更しない。

データセットが空(テンプレートのみ)でもエラーにならず、
0件の結果として benchmarks/results/benchmark_results.csv と
docs/PUBLIC_BENCHMARK_REPORT.md を生成する。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from benchmarks.scripts import _bootstrap  # noqa: F401
from benchmarks.scripts.backtest import build_backtest_pairs, split_standard_and_special_condition_cases
from benchmarks.scripts.cross_org_report import write_cross_organization_diagnostic
from benchmarks.scripts.dataset_io import DEFAULT_DATASET_PATH, load_dataset
from benchmarks.scripts.metrics import RESULT_CSV_COLUMNS, evaluate_pair
from benchmarks.scripts.report import write_report

from app.calculation import constants as calc_constants  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
RESULTS_CSV_PATH = RESULTS_DIR / "benchmark_results.csv"


def run(dataset_path: Path) -> int:
    print(f"[run_backtest] model_version = {calc_constants.MODEL_VERSION} (固定・未変更)")
    print(f"[run_backtest] loading dataset: {dataset_path}")

    dataset = load_dataset(dataset_path)
    print(
        f"[run_backtest] loaded {len(dataset.valid_cases)} valid rows, "
        f"{len(dataset.rejected_cases)} rejected rows (validation errors)"
    )
    for benchmark_id, issues in dataset.issues_by_id.items():
        for issue in issues:
            print(f"  [{issue.severity}] {benchmark_id}.{issue.field}: {issue.message}")

    synthetic_ids = [c.benchmark_id for c in dataset.valid_cases if c.is_synthetic]
    if synthetic_ids:
        print(
            f"[run_backtest] NOTE: {len(synthetic_ids)} row(s) are is_synthetic=true "
            f"(架空データ、実在公演として扱わないこと): {synthetic_ids}"
        )

    # COVID等の特殊条件が明示された公演は、標準のHistorical Backtestの
    # 対象・履歴の両方から除外する(通常校正データへの自動混入防止)。
    standard_cases, special_condition_cases = split_standard_and_special_condition_cases(
        dataset.valid_cases
    )
    if special_condition_cases:
        print(
            f"[run_backtest] NOTE: {len(special_condition_cases)} row(s) are flagged "
            "excluded_from_standard_backtest=true (special conditions; excluded from "
            "both target and history in the standard run):"
        )
        for c in special_condition_cases:
            print(f"    {c.benchmark_id}: {c.exclusion_reason or '(no reason given)'}")

    pairs = build_backtest_pairs(standard_cases)
    results = [evaluate_pair(pair) for pair in pairs]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with RESULTS_CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_CSV_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_row())
    print(f"[run_backtest] wrote {len(results)} result rows -> {RESULTS_CSV_PATH}")

    report_path = write_report(
        dataset, results, calc_constants.MODEL_VERSION, special_condition_cases=special_condition_cases
    )
    print(f"[run_backtest] wrote report -> {report_path}")

    # Cross-organization diagnosticは実在団体の横断比較が目的のため、
    # is_synthetic=true(動作確認用の架空データ)の行は集計に含めない。
    synthetic_id_set = {c.benchmark_id for c in dataset.valid_cases if c.is_synthetic}
    real_results = [r for r in results if r.benchmark_id not in synthetic_id_set]
    cross_org_path = write_cross_organization_diagnostic(real_results, calc_constants.MODEL_VERSION)
    print(f"[run_backtest] wrote cross-organization diagnostic -> {cross_org_path}")

    evaluated = sum(1 for r in results if r.status == "evaluated")
    skipped = sum(1 for r in results if r.status == "skipped")
    print(
        f"[run_backtest] done: evaluated={evaluated} skipped={skipped} "
        f"special_condition_excluded={len(special_condition_cases)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the External Benchmark historical backtest.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the benchmark CSV dataset (default: benchmarks/data/public_performances.csv)",
    )
    args = parser.parse_args()
    return run(args.dataset)


if __name__ == "__main__":
    sys.exit(main())
