"""Benchmark CSVデータセットの読み込み・検証。"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from benchmarks.schema.models import BenchmarkPerformance
from benchmarks.schema.validation import ValidationIssue, has_errors, validate_case

DEFAULT_DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "public_performances.csv"


@dataclass
class DatasetLoadResult:
    valid_cases: list[BenchmarkPerformance] = field(default_factory=list)
    rejected_cases: list[BenchmarkPerformance] = field(default_factory=list)
    issues_by_id: dict[str, list[ValidationIssue]] = field(default_factory=dict)

    @property
    def total_rows(self) -> int:
        return len(self.valid_cases) + len(self.rejected_cases)


def load_dataset(path: Path | str = DEFAULT_DATASET_PATH) -> DatasetLoadResult:
    path = Path(path)
    result = DatasetLoadResult()

    if not path.exists():
        # データセットが存在しない/空でもクラッシュしない(仕様11章)。
        return result

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("benchmark_id"):
                continue  # 空行スキップ
            case = BenchmarkPerformance.from_row(row)
            issues = validate_case(case)
            if issues:
                result.issues_by_id[case.benchmark_id] = issues
            if has_errors(issues):
                result.rejected_cases.append(case)
            else:
                result.valid_cases.append(case)

    return result
