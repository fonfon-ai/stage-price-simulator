# CROSS_ORGANIZATION_DIAGNOSTIC.md

複数団体・複数公演回数にわたるHistorical Backtest結果を横断比較するための診断レポート。特定団体の結果からrule_v0.1の係数・ロジックを変更する判断を行わないための基盤であり、本レポート自体はモデルの変更を一切提案しない(観測のみ)。

- **model_version**: `rule_v0.1`(固定・本レポートは係数を変更しない)
- **対象団体数(target登録済み)**: 4
- **評価済みデータがある団体数**: 2
- **評価済みtarget数(全団体合計)**: 5

## 1. Performance Count Diagnostics(公演回数バケット別)

| bucket | target数 | 評価済 | 完売数 | predicted demand(平均) | demand/performance(平均) | venue capacity(平均) | demand_coverage_ratio(平均) | lower-bound violation率 | Venue Fit | price_gap(平均) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | 0 | 0 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| 2-4 | 0 | 0 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| 5-8 | 7 | 1 | 4 | 2765.5 | 472.2 | 526.0 | 0.657 | 100.0% | slightly_large:1 | 0円 |
| 9-15 | 3 | 0 | 1 | N/A(データ不足で評価不能) | N/A | N/A | N/A | N/A | N/A | N/A |
| 16-20 | 1 | 1 | 1 | 2131.7 | 201.9 | 386.0 | 0.345 | 100.0% | too_large:1 | 6400円 |
| 21+ | 4 | 3 | 3 | 4307.2 | 319.3 | 386.0 | 0.523 | 100.0% | too_large:3 | -567円 |

## 2. History Depth Diagnostics(usable history件数バケット別)

| bucket | 評価済target数 | price_search_boundary_hit率 | predicted demand(平均) | Venue Fit | lower-bound violation率 | price_gap(平均) |
|---|---:|---:|---:|---|---:|---:|
| 1 | 2 | 50.0% | 2448.6 | too_large:1, slightly_large:1 | 100.0% | 3200円 |
| 2 | 1 | 0.0% | 3978.0 | too_large:1 | 100.0% | -900円 |
| 3 | 1 | 0.0% | 4312.4 | too_large:1 | 100.0% | -500円 |
| 4+ | 1 | 0.0% | 4631.2 | too_large:1 | 100.0% | -300円 |

`price_search_boundary_hit` は、推奨価格(balanced_price)が価格探索レンジの最低値または最高値と一致したケースを示す(探索範囲の境界に張り付いた=推奨が不安定である可能性を示唆する)。

## 3. Demand Coverage Ratio

`demand_coverage_ratio = predicted_total_demand / sold_out_lower_bound` (完売公演のみ算出)。1.0未満は「全公演完売」という公開情報とモデル予測が矛盾していることを意味する。performance_countバケット別・団体別の平均値は上記1章・下記5章の表を参照。

- 完売公演のうちdemand_coverage_ratioを算出できた件数: 5
- そのうち1.0未満(公開情報と矛盾)の件数: 5

## 4. Per-performance Demand Diagnostic

`predicted_demand_per_performance` はProduction側の`RuleBasedDemandEstimator.estimate_demand()`を`num_performances=1`で呼び出した正式な値であり、Benchmark側で独自の需要式は作成していない(`benchmarks/scripts/metrics.py` `_per_performance_demand()`参照)。

| benchmark_id | 団体 | predicted_demand_per_performance | actual_venue_capacity(1公演あたり) | 比率 |
|---|---|---:|---:|---:|
| REAL-0005 | シソンヌ | 201.9 | 386 | 0.523 |
| REAL-0006 | シソンヌ | 299.1 | 386 | 0.775 |
| REAL-0007 | シソンヌ | 324.2 | 386 | 0.840 |
| REAL-0008 | シソンヌ | 334.7 | 386 | 0.867 |
| REAL-0015 | かが屋 | 472.2 | 526 | 0.898 |

## 5. Organization-level Report(団体別集計)

「シソンヌ固有の問題」か「複数公演モデル全般の問題」かを判断するための横断比較表。団体が1件のみの場合、この判断はまだ下せない(N/A)。

| 団体 | target数 | 評価済 | 平均performance_count | 平均usable history件数 | price_gap(平均) | demand_coverage_ratio(平均) | lower-bound violation率 | Venue Fit傾向 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| かが屋 | 4 | 1 | 6.0 | 1.0 | 0円 | 0.657 | 100.0% | slightly_large:1 |
| ザ・ギース | 3 | 0 | 8.0 | N/A | N/A | N/A | N/A | N/A(評価済みデータなし) |
| シソンヌ | 6 | 4 | 20.7 | 2.5 | 1175円 | 0.478 | 100.0% | too_large:4 |
| 劇団チョコレートケーキ | 3 | 0 | 12.0 | N/A | N/A | N/A | N/A | N/A(評価済みデータなし) |

## データ品質に関する注意

- 本レポートの集計対象・バケット定義・団体別集計ロジックは、特定団体名をハードコードしていない。新規団体のusable historyが追加されれば、再実行時に自動的に反映される。
- performance_countバケットのうち、現時点で評価済みデータが存在しないものは「N/A(データ不足で評価不能)」と表示している。
