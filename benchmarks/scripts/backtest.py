"""Historical Backtest: 同一団体の複数年データについて、time leakageを防止しつつ
「対象公演より過去の実績のみ」をモデルへ入力する組み合わせを構築する。
"""
from __future__ import annotations

from dataclasses import dataclass

from benchmarks.schema.models import BenchmarkPerformance


@dataclass
class BacktestPair:
    target: BenchmarkPerformance
    history: list[BenchmarkPerformance]


def split_standard_and_special_condition_cases(
    cases: list[BenchmarkPerformance],
) -> tuple[list[BenchmarkPerformance], list[BenchmarkPerformance]]:
    """`excluded_from_standard_backtest=True` の公演を、対象・履歴の両方から除外するために
    標準ケースと特殊条件ケースに分離する(COVID等の混入防止)。"""
    standard = [c for c in cases if not c.excluded_from_standard_backtest]
    special = [c for c in cases if c.excluded_from_standard_backtest]
    return standard, special


def build_backtest_pairs(cases: list[BenchmarkPerformance]) -> list[BacktestPair]:
    """団体ごとに公演を開催日順に並べ、各公演について「それより前に終了した公演のみ」を
    historyとして割り当てる。同一団体名での完全一致グルーピングのみ行う(表記ゆれの
    名寄せは行わない。これは意図的な制限であり、将来の改善余地として明記する)。

    time leakage防止: target.run_start_date 以降に終了した公演は絶対にhistoryへ含めない。
    """
    by_org: dict[str, list[BenchmarkPerformance]] = {}
    for case in cases:
        by_org.setdefault(case.organization_name, []).append(case)

    pairs: list[BacktestPair] = []
    for _, group in by_org.items():
        ordered = sorted(group, key=lambda c: c.run_start_date)
        for i, target in enumerate(ordered):
            history = [c for c in ordered if c.run_end_date < target.run_start_date]
            # 念のための二重チェック: historyに未来公演が絶対に紛れ込んでいないことを保証する。
            assert all(h.run_start_date < target.run_start_date for h in history), (
                f"time leakage detected for {target.benchmark_id}"
            )
            pairs.append(BacktestPair(target=target, history=history))
    return pairs
