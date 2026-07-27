# benchmarks/ — External Benchmark / Historical Backtest 基盤

このディレクトリは、公開情報から収集した**実在公演データ**を使って、
Stage Price Simulator の現行ルールモデル(`model_version = rule_v0.1`)が
過去の公演に対してどのような推奨を出すかを測定するための、
本番ユーザーデータとは完全に独立したベンチマーク基盤である。

**rule_v0.1の27係数(`PRICE_ELASTICITY`、`SOLD_OUT_BASE_CORRECTION` を含む)は一切変更しない。**
`backend/tests/unit/test_model_snapshot.py` がこれを回帰テストとして固定している。
rule_v0.1で発見された構造課題への対応として`rule_v0.2`を並行実装しており(v0.1は変更せず
そのまま維持)、`benchmarks/scripts/compare_model_versions.py`で同一datasetにおける
v0.1/v0.2比較を実行できる。詳細は [docs/RULE_V0_2_DESIGN.md](../docs/RULE_V0_2_DESIGN.md) /
[docs/RULE_V0_2_EVALUATION.md](../docs/RULE_V0_2_EVALUATION.md) を参照。

## ディレクトリ構成

```
benchmarks/
  README.md          このファイル
  schema/             データスキーマ・バリデーション定義(Productionから独立)
  data/               公開情報から収集したCSVデータセット(本番SQLite DBには入れない)
  results/            run_backtest.py の出力(benchmark_results.csv)
  scripts/            データ読み込み・モデル呼び出し・Backtest・レポート生成
  tests/              このディレクトリ専用のpytestテスト
```

本番ユーザーデータ(`backend/theater_pricing.db`)には一切書き込まない。
`benchmarks/scripts/` のコードは `app.db` / `app.models`(本番DB層)を import しない
(`benchmarks/tests/test_isolation.py` で保証)。

## Benchmark Runnerの使い方

```bash
# リポジトリルートから実行(backend/.venv の Python を使用)
backend/.venv/Scripts/python.exe -m benchmarks.scripts.run_backtest

# 別データセットを指定する場合
backend/.venv/Scripts/python.exe -m benchmarks.scripts.run_backtest --dataset benchmarks/data/your_dataset.csv

# rule_v0.1 と rule_v0.2 を同一datasetで比較(docs/RULE_V0_2_EVALUATION.md を生成)
backend/.venv/Scripts/python.exe -m benchmarks.scripts.compare_model_versions
```

実行すると、既存の `RuleBasedDemandEstimator` / `PerformanceSimulator` / `Recommender`
(`backend/app/calculation/`)をそのまま呼び出し、以下を生成する。

- `benchmarks/results/benchmark_results.csv` — 公演ごとの比較指標(performance_count・
  usable history件数・price_search_boundary_hit・demand_coverage_ratio・
  predicted_demand_per_performance等の診断列を含む)
- `docs/PUBLIC_BENCHMARK_REPORT.md` — 集計レポート
- `docs/CROSS_ORGANIZATION_DIAGNOSTIC.md` — performance_countバケット・usable history件数
  バケット・団体別のクロス集計レポート(`benchmarks/scripts/diagnostics.py` /
  `cross_org_report.py`)。特定団体名をハードコードしておらず、新規団体のusable historyが
  `benchmarks/data/public_performances.csv` に追加されれば自動的に横断比較へ反映される。
  is_synthetic=trueの行はこのレポートの集計対象から除外される。

データセットが空、または存在しない場合もエラーにならず、0件の結果として出力される。

## 公開情報を追加する場所

**新しい実在公演データは `benchmarks/data/public_performances.csv` に追記してください。**
列の意味は `benchmarks/schema/models.py` の `BenchmarkPerformance` を参照。

- 実在団体・実在公演のデータを追加する場合、`is_synthetic` は必ず `false`(または空欄)にする。
- `is_synthetic=true` の行(テンプレートに含まれる `SYN-` プレフィックスの行)は
  動作確認用の架空データであり、実在公演として扱ってはならない。
- Claude(AI)自身が実在団体・実在公演のデータを推測して入力することはしない。
  収集はユーザー(人間)が公開情報から行うことを前提とする。

## Historical Backtest の time leakage 防止

同一 `organization_name` の公演を `run_start_date` 順に並べ、対象公演(target)の予測には
「`run_end_date` が target の `run_start_date` より前の公演」のみを past performances として
使用する。target 以降(同時期・未来)の公演情報が特徴量に混入しないことは
`benchmarks/tests/test_backtest.py` で保証している。

団体名は完全一致でグルーピングしており、表記ゆれの名寄せは行わない
(将来の改善余地として明記)。

## 欠損値の扱い

公開情報では実売枚数・稼働率・完売日・会場費・SNSフォロワー数・正確な販売可能席数が
取得できないことが多い。方針:

- 構造上どうしても必要な値(対象公演の venue_capacity、履歴の tickets_sold 相当)が
  欠損している場合は、値を捏造せずそのケースを `skipped` として記録する。
- モデルが要求するが公開情報から取得しづらい値(立地/ブランド評価、SNS等)は、
  「効果が中立(倍率1.0または最も判断を加えない値)になる」ことが説明できる値のみを
  デフォルトとして使用し、`benchmark_results.csv` の `defaulted_fields` 列に
  必ず記録する(詳細は `benchmarks/scripts/model_adapter.py` のコメント参照)。

## Unit Semantics(単位契約) — 重要

Production側(`backend/app/calculation/`)は一貫して「興行全体(run全体、全performance_count回合計)」
単位で需要・売上・利益を計算する(`docs/DEMAND_SEMANTICS_AUDIT.md` 参照)。Benchmark側のデータも
この契約に合わせる必要がある。

| フィールド | 単位 |
|---|---|
| `performance_count` | 対象run(この benchmark_id が表す公演期間)に含まれる公演回数 |
| `venue_capacity` | **1公演あたり**の物理的または販売可能な客席数(run全体の延べ席数ではない) |
| `observed_attendance` | 対象**run全体**(performance_count回分の合計)の総販売枚数/総来場数 |

興行全体の延べ販売可能席数が必要な場面では、必ず `venue_capacity × performance_count` を計算する。
`venue_capacity` 単体をrun全体の値として扱ってはならない
(過去にこの単位混同がバグとして発生し、`docs/DEMAND_SEMANTICS_AUDIT.md` および
`docs/PUBLIC_BENCHMARK_REPORT.md` の「Benchmark Unit Bug」節に修正記録がある)。

## Censored / Sold-out の扱い

完売公演の実売数を「真の需要そのもの」として扱わない。`observed_attendance` が不明で
`sold_out_status=all_sold_out` かつ `venue_capacity`・`performance_count` の両方が既知の場合、
**`venue_capacity × performance_count`**(run全体の延べ席数)を実需要の**下限(lower bound)**として
使用する(`venue_capacity`単体ではない)。`performance_count`が不明な場合は推測せず、
その公演は usable history として使用しない。

モデルの予測需要がこの下限を下回っていないかを `sold_out_lower_bound_violation` 列で報告する
(真であれば、モデル予測が公開情報と矛盾している可能性を示す)。

## Model Version の固定

`benchmark_results.csv` の全行に `model_version` 列(現在 `rule_v0.1`)を保存する。
係数のスナップショットは `backend/app/calculation/model_snapshot.py` から取得できる。
