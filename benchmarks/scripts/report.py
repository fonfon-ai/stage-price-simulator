"""docs/PUBLIC_BENCHMARK_REPORT.md を生成する。データセットが空でも動作する。"""
from __future__ import annotations

import statistics
from pathlib import Path

from benchmarks.schema.models import BenchmarkPerformance
from benchmarks.scripts.dataset_io import DatasetLoadResult
from benchmarks.scripts.metrics import BenchmarkResult

OPTIONAL_FIELDS_FOR_MISSING_RATE = [
    "venue_capacity",
    "observed_attendance",
    "sns_x_followers",
    "sns_instagram_followers",
    "sns_youtube_subscribers",
    "sns_other_followers",
    "venue_location_rating",
    "venue_brand_rating",
    "venue_cost",
    "is_new_work",
    "is_weekend_holiday",
    "is_evening",
    "rarity_level",
    "has_guest",
    "is_special",
]


def _missing_rate(cases: list[BenchmarkPerformance]) -> float:
    if not cases:
        return 0.0
    total = 0
    missing = 0
    for case in cases:
        for field_name in OPTIONAL_FIELDS_FOR_MISSING_RATE:
            total += 1
            if getattr(case, field_name) is None:
                missing += 1
    return missing / total if total else 0.0


def _primary_source_rate(cases: list[BenchmarkPerformance]) -> float | None:
    with_confidence = [c for c in cases if c.confidence is not None]
    if not with_confidence:
        return None
    primary = sum(1 for c in with_confidence if c.confidence is not None and c.confidence.value == "A")
    return primary / len(with_confidence)


def _fmt_pct(v: float | None) -> str:
    return "N/A" if v is None else f"{v * 100:.1f}%"


def _fmt_num(v: float | None, digits: int = 1) -> str:
    return "N/A" if v is None else f"{v:.{digits}f}"


def _benchmark_unit_bug_history_section() -> list[str]:
    """Benchmark Unit Bug の恒久的な履歴記録。

    このセクションは現在の実行結果から動的に生成されるものではなく、過去に発見・修正された
    Benchmark adapter/metrics側の単位不整合(DEMAND_SEMANTICS_AUDIT.md)の記録として、
    レポート再生成後も消えないよう固定テキストとして埋め込んでいる。
    再現可能な研究記録として、修正前後の実測値をそのまま残す。
    """
    lines: list[str] = []
    lines.append("## Benchmark Unit Bug(履歴記録・恒久保存)")
    lines.append("")
    lines.append(
        "**何が間違っていたか**: `benchmarks/scripts/model_adapter.py` の "
        "`_derive_tickets_sold()` が、`sold_out_status=all_sold_out` かつ "
        "`observed_attendance` 不明の履歴に対し、`venue_capacity`(1公演あたりの客席数)を "
        "そのまま `PastPerformance.tickets_sold`(Production側の契約では"
        "「run全体・全performance_count回分の合計販売枚数」)へ代入していた。"
        "さらに `benchmarks/scripts/metrics.py` の `recommended_capacity_low/high` が、"
        "興行全体(run全体)単位の `expected_demand` を `num_performances` で"
        "割り戻さずにそのまま `actual_venue_capacity`(1公演あたり単位)と並べて報告していた。"
    )
    lines.append("")
    lines.append(
        "**なぜ発生したか**: Production側(`docs/DATA_MODEL.md`、`demand_estimator.py`)は "
        "`tickets_sold` を一貫して「run全体合計」として扱う契約になっているが、"
        "Benchmark側のスキーマ(`benchmarks/schema/models.py`)に `venue_capacity`・"
        "`observed_attendance`・`performance_count` の単位契約が明記されておらず、"
        "adapter実装時に「1公演あたりのcapacityを完売の下限としてそのまま使う」という"
        "誤った実装が入り込んだ。"
    )
    lines.append("")
    lines.append(
        "**どの指標に影響したか**: `predicted_demand_at_actual_price`、`balanced_price`、"
        "`price_gap`/`percentage_price_gap`、`sold_out_lower_bound_violation`、"
        "`venue_fit_at_actual_price`、`recommended_capacity_low/high`。"
        "詳細は `docs/DEMAND_SEMANTICS_AUDIT.md` を参照。"
    )
    lines.append("")
    lines.append("**修正内容**:")
    lines.append(
        "1. `_derive_tickets_sold()`: `venue_capacity` → `venue_capacity × performance_count`"
        "(performance_count不明の場合は引き続き推測せず除外)。"
    )
    lines.append(
        "2. `recommended_capacity_low/high`: Production側の `estimate_demand()` を "
        "`num_performances=1` で再呼び出しし(独自の変換式を新設せず既存ロジックを再利用)、"
        "1公演あたり単位に揃えてから算出するよう変更。"
    )
    lines.append("3. schemaのdocstring・`benchmarks/README.md` に各フィールドの単位契約を明記。")
    lines.append("")
    lines.append("**修正前後の実測値(シソンヌ、2025-07-27時点のデータセットに対する実行)**:")
    lines.append("")
    lines.append(
        "| target年 | 行 | actual price | balanced BEFORE | balanced AFTER | "
        "predicted demand BEFORE | predicted demand AFTER | "
        "lower-bound violation BEFORE/AFTER | Venue Fit BEFORE/AFTER |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---|---|")
    lines.append(
        "| 2022 | REAL-0005 | 8,000円 | 14,400円 | 14,400円 | 152.3 | 2,131.7 | "
        "True / True | too_large / too_large |"
    )
    lines.append(
        "| 2023 | REAL-0006 | 8,000円 | 7,600円 | 7,100円 | 261.9 | 3,978.0 | "
        "True / True | too_large / too_large |"
    )
    lines.append(
        "| 2024 | REAL-0007 | 8,000円 | 8,200円 | 7,500円 | 243.9 | 4,312.4 | "
        "True / True | too_large / too_large |"
    )
    lines.append(
        "| 2025 | REAL-0008 | 8,000円 | 8,500円 | 7,700円 | 242.9 | 4,631.2 | "
        "True / True | too_large / too_large |"
    )
    lines.append("")
    lines.append(
        "**修正の効果**: predicted demandは修正により約14〜19倍に増加した"
        "(REAL-0002由来の`386`が`386×14=5,404`相当に是正されたため、後続の全targetへ連鎖的に反映)。"
        "一方、`sold_out_lower_bound_violation`は修正後も4件全てTrueのまま、"
        "`Venue Fit`も4件全てtoo_largeのままだった。**これは単位を揃えた上でなお観測された"
        "結果であり、以後はBenchmarkバグではなくrule_v0.1本体(特にPOOL_EXPONENTによる"
        "観客プール逓減の仮定)の挙動として評価対象とする。** 2022年(REAL-0005)の"
        "balanced_priceが実売の+80%になる問題は、履歴がREAL-0002(2019)1件のみで"
        "薄いという条件下では修正後も解消しなかった(価格探索レンジの上限で頭打ちになっている)。"
        "2023年以降は履歴が2件以上に増えるにつれ、balanced_priceが実売価格に対し"
        "-11.25%→-6.25%→-3.75%と収束方向に推移している(修正前は+80%→-5.0%→+2.5%→+6.25%で"
        "符号が安定しない推移だった)。"
    )
    lines.append("")
    return lines


def build_report_markdown(
    dataset: DatasetLoadResult,
    results: list[BenchmarkResult],
    model_version: str,
    special_condition_cases: list[BenchmarkPerformance] | None = None,
) -> str:
    special_condition_cases = special_condition_cases or []
    all_cases = dataset.valid_cases
    synthetic_ids = {c.benchmark_id for c in all_cases if c.is_synthetic}
    real_cases = [c for c in all_cases if not c.is_synthetic]

    evaluated_all = [r for r in results if r.status == "evaluated"]
    skipped_all = [r for r in results if r.status == "skipped"]
    # 合成データ(is_synthetic=true)の評価結果は動作確認用であり、実在公演の統計に
    # 混ぜない(要件: SYN-行はis_syntheticのまま明確に分離する)。
    evaluated = [r for r in evaluated_all if r.benchmark_id not in synthetic_ids]
    evaluated_synthetic = [r for r in evaluated_all if r.benchmark_id in synthetic_ids]
    skipped = [r for r in skipped_all if r.benchmark_id not in synthetic_ids]
    skipped_synthetic = [r for r in skipped_all if r.benchmark_id in synthetic_ids]

    orgs = sorted({c.organization_name for c in real_cases})
    dates = [c.run_start_date for c in real_cases]
    period = f"{min(dates)} 〜 {max(dates)}" if dates else "N/A(データなし)"

    price_gaps = [r.price_gap for r in evaluated if r.price_gap is not None]
    pct_gaps = [r.percentage_price_gap for r in evaluated if r.percentage_price_gap is not None]

    sold_out_evaluated = [r for r in evaluated if r.sold_out_lower_bound_violation is not None]
    violations = [r for r in sold_out_evaluated if r.sold_out_lower_bound_violation]

    venue_fit_counts: dict[str, int] = {}
    for r in evaluated:
        if r.venue_fit_at_actual_price:
            venue_fit_counts[r.venue_fit_at_actual_price] = (
                venue_fit_counts.get(r.venue_fit_at_actual_price, 0) + 1
            )

    lines: list[str] = []
    lines.append("# PUBLIC_BENCHMARK_REPORT.md")
    lines.append("")
    lines.append(
        "External Benchmark / Historical Backtest の結果報告。"
        "公開情報から収集した実在公演データに対し、Production側のルールモデルが"
        "どのような推奨を出すかを測定したものであり、モデルの係数は一切調整していない。"
    )
    lines.append("")
    lines.append(f"- **model_version**: `{model_version}`(固定・本フェーズ中は変更なし)")
    lines.append(f"- **使用団体数(実在データのみ)**: {len(orgs)}")
    lines.append(f"- **使用公演数(実在データ)**: {len(real_cases)}")
    lines.append(
        f"- **is_synthetic=true(架空・動作確認用)の行数**: {len(synthetic_ids)}"
        "(以下の統計からは除外)"
    )
    lines.append(f"- **拒否された公演数(validation error)**: {len(dataset.rejected_cases)}")
    lines.append(f"- **データ取得期間(run_start_dateの範囲、実在データ)**: {period}")
    lines.append(f"- **データ欠損率(主要な補助特徴量ベース、実在データ)**: {_fmt_pct(_missing_rate(real_cases))}")
    lines.append(f"- **一次情報(confidence=A)比率(実在データ)**: {_fmt_pct(_primary_source_rate(real_cases))}")
    lines.append(
        f"- **Backtest評価対象(実在データ)**: {len(evaluated)}件 / "
        f"**スキップ(実在データ)**: {len(skipped)}件"
    )
    lines.append(
        f"- **特殊条件(COVID等)により標準backtestから除外**: {len(special_condition_cases)}件"
    )
    if evaluated_synthetic:
        lines.append(
            f"- **注意**: `run_backtest.py` のコンソール出力・`benchmark_results.csv` 全体で見た"
            f"`evaluated` 件数は **{len(evaluated) + len(evaluated_synthetic)}件**"
            f"(実在データ{len(evaluated)}件 + is_synthetic=true のデータ{len(evaluated_synthetic)}件)。"
            "本レポートおよび `docs/RULE_V0_2_EVALUATION.md` の集計は一貫してis_synthetic=trueを"
            "含めない実在データのみを使用しており、意図された差である"
            "(架空データを実在団体の評価指標に混入させないため)。"
        )
    lines.append("")

    lines.extend(_benchmark_unit_bug_history_section())

    lines.append("## 合成データ(is_synthetic=true)の動作確認結果 — 参考情報")
    lines.append("")
    lines.append(
        "以下はパイプライン自体の動作確認用の架空データ(`SYN-`プレフィックス)の結果であり、"
        "**実在公演の統計には一切含めていない**。"
    )
    lines.append("")
    if evaluated_synthetic:
        for r in evaluated_synthetic:
            lines.append(
                f"- {r.benchmark_id}: actual={r.actual_ticket_price}円 balanced={r.balanced_price}円 "
                f"(price_gap={r.price_gap}円, {_fmt_num(r.percentage_price_gap)}%), "
                f"venue_fit={r.venue_fit_at_actual_price}, "
                f"sold_out_lower_bound_violation={r.sold_out_lower_bound_violation}"
            )
    if skipped_synthetic:
        for r in skipped_synthetic:
            lines.append(f"- {r.benchmark_id}: skipped ({r.skip_reason})")
    if not evaluated_synthetic and not skipped_synthetic:
        lines.append("該当なし。")
    lines.append("")

    lines.append("## Actual Price と Recommended Price の差(実在データのみ)")
    lines.append("")
    lines.append(
        "注意: `actual_ticket_price` は「最適価格の正解ラベル」ではなく、あくまで比較対象の実績値である。"
    )
    lines.append("")
    if price_gaps:
        lines.append(f"- price_gap(balanced_price - actual_price) 平均: {_fmt_num(statistics.mean(price_gaps), 0)}円")
        lines.append(f"- price_gap 中央値: {_fmt_num(statistics.median(price_gaps), 0)}円")
        lines.append(f"- percentage_price_gap 平均: {_fmt_num(statistics.mean(pct_gaps))}%")
        lines.append(f"- percentage_price_gap 中央値: {_fmt_num(statistics.median(pct_gaps))}%")
    else:
        lines.append("- 評価対象データがないため算出不可(N/A)")
    lines.append("")

    lines.append("## Sold-out Lower-bound Violation(実在データ)")
    lines.append("")
    lines.append(
        f"- 完売公演のうち lower-bound 評価が可能だった件数: {len(sold_out_evaluated)}"
    )
    lines.append(f"- lower-bound違反件数(モデル予測 < 実際の販売可能席数): {len(violations)}")
    if violations:
        lines.append("")
        lines.append("違反したケース:")
        for r in violations:
            lines.append(
                f"- {r.benchmark_id} ({r.organization_name} / {r.production_name}): "
                f"predicted={_fmt_num(r.predicted_demand_at_actual_price, 1)}"
            )
    lines.append("")

    lines.append("## Venue Fit の傾向(実売価格時点、実在データ)")
    lines.append("")
    if venue_fit_counts:
        for k, v in sorted(venue_fit_counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {k}: {v}件")
    else:
        lines.append("- 評価対象データがないため算出不可(N/A)")
    lines.append("")

    lines.append("## 団体別結果(実在データ)")
    lines.append("")
    if evaluated:
        by_org: dict[str, list[BenchmarkResult]] = {}
        for r in evaluated:
            by_org.setdefault(r.organization_name, []).append(r)
        lines.append("| 団体 | 評価件数 | price_gap平均 | percentage_price_gap平均 |")
        lines.append("|---|---:|---:|---:|")
        for org, rs in sorted(by_org.items()):
            gaps = [r.price_gap for r in rs if r.price_gap is not None]
            pcts = [r.percentage_price_gap for r in rs if r.percentage_price_gap is not None]
            lines.append(
                f"| {org} | {len(rs)} | {_fmt_num(statistics.mean(gaps), 0) if gaps else 'N/A'}円 "
                f"| {_fmt_num(statistics.mean(pcts)) if pcts else 'N/A'}% |"
            )
    else:
        lines.append("評価対象データがないため N/A。")
    lines.append("")

    lines.append("## 特殊条件(COVID等)により標準backtestから除外した公演")
    lines.append("")
    lines.append(
        "notesにCOVID等の特殊事情が記載されていても自動判定はせず、"
        "`excluded_from_standard_backtest=true` が明示された行のみを対象・履歴の両方から除外している。"
    )
    lines.append("")
    if special_condition_cases:
        for c in special_condition_cases:
            lines.append(
                f"- {c.benchmark_id} ({c.organization_name} / {c.production_name}): "
                f"{c.exclusion_reason or '(理由未記入)'}"
            )
    else:
        lines.append("該当する公演はありません。")
    lines.append("")

    lines.append("## スキップされたケース(実在データ、データ不足で評価不能だったもの)")
    lines.append("")
    if skipped:
        reason_counts: dict[str, int] = {}
        for r in skipped:
            reason_counts[r.skip_reason or "unknown"] = reason_counts.get(r.skip_reason or "unknown", 0) + 1
        for reason, count in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {reason}: {count}件")
        lines.append("")
        lines.append("内訳:")
        for r in skipped:
            lines.append(f"- {r.benchmark_id} ({r.organization_name} / {r.production_name}): {r.skip_reason}")
    else:
        lines.append("スキップされたケースはありません(またはデータセットが空です)。")
    lines.append("")

    lines.append("## モデルが明らかに不自然だったケース(実在データ)")
    lines.append("")
    unnatural = [
        r for r in evaluated
        if (r.percentage_price_gap is not None and abs(r.percentage_price_gap) >= 100)
        or r.sold_out_lower_bound_violation
    ]
    if unnatural:
        for r in unnatural:
            lines.append(
                f"- {r.benchmark_id} ({r.organization_name}): "
                f"actual={r.actual_ticket_price}円 balanced={r.balanced_price}円 "
                f"(gap={_fmt_num(r.percentage_price_gap)}%), "
                f"lower_bound_violation={r.sold_out_lower_bound_violation}"
            )
    else:
        lines.append("該当するケースはありません(またはデータセットが空です)。")
    lines.append("")

    no_history_count = sum(1 for r in skipped if r.skip_reason == "no_usable_history")
    if real_cases and no_history_count:
        lines.append("## 主要な観察: 実在データがHistorical Backtestで評価不能になった理由")
        lines.append("")
        lines.append(
            f"実在データ{len(real_cases)}件中{no_history_count}件が `no_usable_history` "
            "(履歴として使える過去公演がゼロ)でスキップされた。原因は rule_v0.1 の係数ではなく、"
            "`model_adapter.py` の censored data 処理方針にある:"
        )
        lines.append("")
        lines.append(
            "- 過去公演をPastPerformanceとして使うには `tickets_sold` 相当の値が必要。"
            "これは (a) `observed_attendance` が既知、または (b) `sold_out_status=all_sold_out` "
            "かつ `venue_capacity` が既知、のいずれかでなければ導出できない(捏造しない方針のため)。"
        )
        lines.append(
            "- 今回のバッチでは `sold_out_status=unknown` かつ `observed_attendance` 未記入の"
            "行が多く、同一団体の過去公演がすべてこの状態だと、対象公演に使える履歴が"
            "ゼロになりHistorical Backtestが実行できない。"
        )
        lines.append(
            "- これはモデルの推奨精度の問題ではなく、**公開情報から実売数・完売状況を"
            "確認できる公演がまだ少ない**というデータ収集側の制約である。今後のバッチでは、"
            "`observed_attendance`(reported_totalでも可)または`sold_out_status`+`venue_capacity`"
            "の組み合わせを優先的に収集すると、評価可能件数を増やせる見込み。"
        )
        lines.append("")

    lines.append("## データ品質に関する注意")
    lines.append("")
    lines.append(
        "- このレポートに含まれる数値は、公開情報の収集状況に強く依存する。"
        "件数が少ない場合の平均値・傾向は参考程度に留めること。"
    )
    lines.append(
        "- `defaulted_fields` が付与された評価は、立地/ブランド評価・SNS・平日祝日等の"
        "補助特徴量が公開情報から取得できず、ニュートラルな既定値で代替されたことを意味する"
        "(`benchmarks/results/benchmark_results.csv` の該当列を参照)。"
    )
    lines.append("")

    return "\n".join(lines)


def write_report(
    dataset: DatasetLoadResult,
    results: list[BenchmarkResult],
    model_version: str,
    docs_dir: Path | None = None,
    special_condition_cases: list[BenchmarkPerformance] | None = None,
) -> Path:
    if docs_dir is None:
        docs_dir = Path(__file__).resolve().parents[2] / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_path = docs_dir / "PUBLIC_BENCHMARK_REPORT.md"
    out_path.write_text(
        build_report_markdown(dataset, results, model_version, special_condition_cases),
        encoding="utf-8",
    )
    return out_path
