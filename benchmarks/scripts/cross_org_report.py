"""docs/CROSS_ORGANIZATION_DIAGNOSTIC.md を生成する。

シソンヌ以外の団体データが増えるたびに、このレポートは自動的に横断比較対象へ
組み込まれる(団体名でグルーピングしているだけで、特定団体名をハードコードしていない)。
現時点でデータが不足しているbucket/団体はN/Aとして明示する。
"""
from __future__ import annotations

from pathlib import Path

from benchmarks.scripts.diagnostics import (
    BucketStats,
    aggregate_by_history_depth,
    aggregate_by_organization,
    aggregate_by_performance_count,
)
from benchmarks.scripts.metrics import BenchmarkResult


def _fmt(v: float | None, digits: int = 1, suffix: str = "") -> str:
    return "N/A" if v is None else f"{v:.{digits}f}{suffix}"


def _fmt_pct(v: float | None) -> str:
    return "N/A" if v is None else f"{v * 100:.1f}%"


def _venue_fit_str(dist: dict[str, int]) -> str:
    if not dist:
        return "N/A"
    return ", ".join(f"{k}:{v}" for k, v in sorted(dist.items(), key=lambda kv: -kv[1]))


def _bucket_table(title: str, stats: dict[str, BucketStats], order: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    lines.append(
        "| bucket | target数 | 評価済 | 完売数 | predicted demand(平均) | "
        "demand/performance(平均) | venue capacity(平均) | demand_coverage_ratio(平均) | "
        "lower-bound violation率 | Venue Fit | price_gap(平均) |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for label in order:
        s = stats.get(label)
        if s is None or s.target_count == 0:
            lines.append(f"| {label} | 0 | 0 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")
            continue
        if not s.has_evaluated_data:
            lines.append(
                f"| {label} | {s.target_count} | 0 | {s.sold_out_count} | "
                "N/A(データ不足で評価不能) | N/A | N/A | N/A | N/A | N/A | N/A |"
            )
            continue
        lines.append(
            f"| {label} | {s.target_count} | {s.evaluated_count} | {s.sold_out_count} | "
            f"{_fmt(s.avg_predicted_demand_at_actual_price, 1)} | "
            f"{_fmt(s.avg_predicted_demand_per_performance, 1)} | "
            f"{_fmt(s.avg_actual_venue_capacity, 1)} | "
            f"{_fmt(s.avg_demand_coverage_ratio, 3)} | "
            f"{_fmt_pct(s.sold_out_lower_bound_violation_rate)} | "
            f"{_venue_fit_str(s.venue_fit_distribution)} | "
            f"{_fmt(s.avg_price_gap, 0)}円 |"
        )
    lines.append("")
    return lines


def build_cross_organization_diagnostic_markdown(
    results: list[BenchmarkResult], model_version: str
) -> str:
    evaluated_all = [r for r in results if r.status == "evaluated"]
    organizations = sorted({r.organization_name for r in results})

    lines: list[str] = []
    lines.append("# CROSS_ORGANIZATION_DIAGNOSTIC.md")
    lines.append("")
    lines.append(
        "複数団体・複数公演回数にわたるHistorical Backtest結果を横断比較するための診断レポート。"
        "特定団体の結果からrule_v0.1の係数・ロジックを変更する判断を行わないための基盤であり、"
        "本レポート自体はモデルの変更を一切提案しない(観測のみ)。"
    )
    lines.append("")
    orgs_with_evaluated_data = sorted({r.organization_name for r in evaluated_all})
    lines.append(f"- **model_version**: `{model_version}`(固定・本レポートは係数を変更しない)")
    lines.append(f"- **対象団体数(target登録済み)**: {len(organizations)}")
    lines.append(f"- **評価済みデータがある団体数**: {len(orgs_with_evaluated_data)}")
    lines.append(f"- **評価済みtarget数(全団体合計)**: {len(evaluated_all)}")
    if len(orgs_with_evaluated_data) <= 1:
        lines.append(
            "- **注意**: 現時点で評価可能な(usable historyが揃っている)実績データがあるのは"
            f"{'団体「' + orgs_with_evaluated_data[0] + '」のみ' if orgs_with_evaluated_data else '0団体'}"
            "です。他団体はtargetとして登録されているものの、usable historyの不足によりまだ"
            "評価できていません(5章の表を参照)。以下の集計のうち団体間比較が必要な箇所は、"
            "他団体のusable historyが蓄積されるまでN/A、または実質的に単一団体の結果として"
            "解釈してください。本レポートの集計ロジックは団体名をハードコードしておらず、"
            "今後ザ・ギース、かが屋、劇団チョコレートケーキ等のusable historyが増えれば"
            "自動的に横断比較へ反映されます。"
        )
    lines.append("")

    # --- 1. Performance Count Diagnostics ---
    pc_stats = aggregate_by_performance_count(results)
    pc_order = ["1", "2-4", "5-8", "9-15", "16-20", "21+"]
    lines.extend(
        _bucket_table("1. Performance Count Diagnostics(公演回数バケット別)", pc_stats, pc_order)
    )

    # --- 2. History Depth Diagnostics ---
    hd_stats = aggregate_by_history_depth(results)
    hd_order = ["1", "2", "3", "4+"]
    lines.append("## 2. History Depth Diagnostics(usable history件数バケット別)")
    lines.append("")
    lines.append(
        "| bucket | 評価済target数 | price_search_boundary_hit率 | predicted demand(平均) | "
        "Venue Fit | lower-bound violation率 | price_gap(平均) |"
    )
    lines.append("|---|---:|---:|---:|---|---:|---:|")
    for label in hd_order:
        s = hd_stats.get(label)
        if s is None or not s.has_evaluated_data:
            lines.append(f"| {label} | 0 | N/A | N/A | N/A | N/A | N/A |")
            continue
        lines.append(
            f"| {label} | {s.evaluated_count} | "
            f"{_fmt_pct(s.price_search_boundary_hit_rate)} | "
            f"{_fmt(s.avg_predicted_demand_at_actual_price, 1)} | "
            f"{_venue_fit_str(s.venue_fit_distribution)} | "
            f"{_fmt_pct(s.sold_out_lower_bound_violation_rate)} | "
            f"{_fmt(s.avg_price_gap, 0)}円 |"
        )
    lines.append("")
    lines.append(
        "`price_search_boundary_hit` は、推奨価格(balanced_price)が価格探索レンジの"
        "最低値または最高値と一致したケースを示す(探索範囲の境界に張り付いた=推奨が"
        "不安定である可能性を示唆する)。"
    )
    lines.append("")

    # --- 3. Demand Coverage Ratio (already embedded in bucket tables, add explicit note) ---
    lines.append("## 3. Demand Coverage Ratio")
    lines.append("")
    lines.append(
        "`demand_coverage_ratio = predicted_total_demand / sold_out_lower_bound` "
        "(完売公演のみ算出)。1.0未満は「全公演完売」という公開情報とモデル予測が"
        "矛盾していることを意味する。performance_countバケット別・団体別の平均値は"
        "上記1章・下記5章の表を参照。"
    )
    lines.append("")
    sold_out_evaluated = [r for r in evaluated_all if r.sold_out_status == "all_sold_out"]
    ratios = [r.demand_coverage_ratio for r in sold_out_evaluated if r.demand_coverage_ratio is not None]
    if ratios:
        below_one = sum(1 for r in ratios if r < 1.0)
        lines.append(
            f"- 完売公演のうちdemand_coverage_ratioを算出できた件数: {len(ratios)}"
        )
        lines.append(f"- そのうち1.0未満(公開情報と矛盾)の件数: {below_one}")
    else:
        lines.append("- 現時点でdemand_coverage_ratioを算出できた完売公演はありません(N/A)。")
    lines.append("")

    # --- 4. Per-performance Demand Diagnostic ---
    lines.append("## 4. Per-performance Demand Diagnostic")
    lines.append("")
    lines.append(
        "`predicted_demand_per_performance` はProduction側の`RuleBasedDemandEstimator."
        "estimate_demand()`を`num_performances=1`で呼び出した正式な値であり、"
        "Benchmark側で独自の需要式は作成していない(`benchmarks/scripts/metrics.py` "
        "`_per_performance_demand()`参照)。"
    )
    lines.append("")
    if evaluated_all:
        lines.append(
            "| benchmark_id | 団体 | predicted_demand_per_performance | "
            "actual_venue_capacity(1公演あたり) | 比率 |"
        )
        lines.append("|---|---|---:|---:|---:|")
        for r in evaluated_all:
            ratio = (
                f"{r.demand_per_performance_to_capacity_ratio:.3f}"
                if r.demand_per_performance_to_capacity_ratio is not None
                else "N/A"
            )
            cap = r.actual_venue_capacity if r.actual_venue_capacity is not None else "N/A"
            dpp = (
                f"{r.predicted_demand_per_performance:.1f}"
                if r.predicted_demand_per_performance is not None
                else "N/A"
            )
            lines.append(f"| {r.benchmark_id} | {r.organization_name} | {dpp} | {cap} | {ratio} |")
    else:
        lines.append("評価済みtargetがないためN/A。")
    lines.append("")

    # --- 5. Organization-level Report ---
    org_stats = aggregate_by_organization(results)
    lines.append("## 5. Organization-level Report(団体別集計)")
    lines.append("")
    lines.append(
        "「シソンヌ固有の問題」か「複数公演モデル全般の問題」かを判断するための横断比較表。"
        "団体が1件のみの場合、この判断はまだ下せない(N/A)。"
    )
    lines.append("")
    lines.append(
        "| 団体 | target数 | 評価済 | 平均performance_count | 平均usable history件数 | "
        "price_gap(平均) | demand_coverage_ratio(平均) | lower-bound violation率 | Venue Fit傾向 |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for org in sorted(org_stats.keys()):
        org_stat = org_stats[org]
        if org_stat.evaluated_count == 0:
            lines.append(
                f"| {org} | {org_stat.target_count} | 0 | "
                f"{_fmt(org_stat.avg_performance_count, 1)} | N/A | N/A | N/A | N/A | "
                "N/A(評価済みデータなし) |"
            )
            continue
        lines.append(
            f"| {org} | {org_stat.target_count} | {org_stat.evaluated_count} | "
            f"{_fmt(org_stat.avg_performance_count, 1)} | "
            f"{_fmt(org_stat.avg_usable_history_count, 1)} | "
            f"{_fmt(org_stat.avg_price_gap, 0)}円 | "
            f"{_fmt(org_stat.avg_demand_coverage_ratio, 3)} | "
            f"{_fmt_pct(org_stat.sold_out_lower_bound_violation_rate)} | "
            f"{_venue_fit_str(org_stat.venue_fit_distribution)} |"
        )
    lines.append("")
    if len(organizations) <= 1:
        lines.append(
            "**現時点では団体が1件(シソンヌ)のみのため、「シソンヌ固有」か「複数公演モデル"
            "全般」かの判定はできない(B: データ不足で判断不能)。** "
            "ザ・ギース、かが屋、劇団チョコレートケーキ等について、`sold_out_status`+"
            "`venue_capacity`+`performance_count`、または`observed_attendance`が揃った"
            "usable historyが `benchmarks/data/public_performances.csv` に追加され次第、"
            "この表は自動的に複数行へ拡張され、横断比較が可能になる。"
        )
        lines.append("")

    lines.append("## データ品質に関する注意")
    lines.append("")
    lines.append(
        "- 本レポートの集計対象・バケット定義・団体別集計ロジックは、特定団体名を"
        "ハードコードしていない。新規団体のusable historyが追加されれば、"
        "再実行時に自動的に反映される。"
    )
    lines.append(
        "- performance_countバケットのうち、現時点で評価済みデータが存在しないものは"
        "「N/A(データ不足で評価不能)」と表示している。"
    )
    lines.append("")

    return "\n".join(lines)


def write_cross_organization_diagnostic(
    results: list[BenchmarkResult], model_version: str, docs_dir: Path | None = None
) -> Path:
    if docs_dir is None:
        docs_dir = Path(__file__).resolve().parents[2] / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_path = docs_dir / "CROSS_ORGANIZATION_DIAGNOSTIC.md"
    out_path.write_text(
        build_cross_organization_diagnostic_markdown(results, model_version), encoding="utf-8"
    )
    return out_path
