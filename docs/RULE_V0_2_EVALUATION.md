# RULE_V0_2_EVALUATION.md

rule_v0.1 と rule_v0.2 を同一の実在benchmark dataset(`benchmarks/data/public_performances.csv`)でHistorical Backtestし比較した結果。

## 評価原則(重要)

**「実売価格(actual_ticket_price)に近づいたからv0.2が優れている」とは評価しない。**実売価格は最適価格の正解ラベルではない。優先順位は以下の通り:

1. 公開された事実(全公演完売等)と矛盾しないか(demand_coverage_ratio)
2. 既存Invariantを壊していないか
3. Cold Start(履歴が薄い場合)で極端な推奨を無警告で出さないか
4. 価格推奨の安定性
5. 実価格との差は参考指標に過ぎない(最下位の優先度)

## 実在データでの比較(評価済みtargetのみ)

| benchmark_id | 団体 | actual price | balanced v0.1 | balanced v0.2 | gap% v0.1 | gap% v0.2 | total demand v0.1 | total demand v0.2 | coverage v0.1 | coverage v0.2 | violation v0.1/v0.2 | Venue Fit v0.1/v0.2 | boundary_hit v0.1/v0.2 | usable_history |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|
| REAL-0005 | シソンヌ | 8000円 | 14400円 | 14400円 | 80.0% | 80.0% | 2131.7 | 2611.3 | 0.345 | 0.423 | True/True | too_large/too_large | True/True | 1 |
| REAL-0006 | シソンヌ | 8000円 | 7100円 | 6900円 | -11.2% | -13.8% | 3978.0 | 4911.0 | 0.491 | 0.606 | True/True | too_large/slightly_large | False/False | 2 |
| REAL-0007 | シソンヌ | 8000円 | 7500円 | 7500円 | -6.2% | -6.2% | 4312.4 | 5323.8 | 0.532 | 0.657 | True/True | too_large/slightly_large | False/False | 3 |
| REAL-0008 | シソンヌ | 8000円 | 7700円 | 7700円 | -3.8% | -3.8% | 4631.2 | 5724.3 | 0.545 | 0.674 | True/True | too_large/slightly_large | False/False | 4 |
| REAL-0015 | かが屋 | 4500円 | 4500円 | 4500円 | 0.0% | 0.0% | 2765.5 | 3301.8 | 0.657 | 0.785 | True/True | slightly_large/good | False/False | 1 |
| REAL-0020 | 劇団チョコレートケーキ | 5000円 | 4100円 | 4000円 | -18.0% | -20.0% | 1105.9 | 1337.6 | N/A | N/A | None/None | too_large/slightly_large | False/False | 1 |

## 合成データ(is_synthetic=true)での比較 — 参考情報

実在団体の評価には一切含めていない、動作確認用の架空データの比較。

- SYN-0001: balanced v0.1=3600円 / v0.2=3600円, coverage v0.1=0.159 / v0.2=0.183
- SYN-0002: skipped (no_usable_history)

## Cold Start比較(usable_history_count別)

| usable_history_count | 件数 | boundary_hit率 v0.1 | boundary_hit率 v0.2 | data_sufficiency | strong_recommendation_allowed |
|---:|---:|---:|---:|---|---|
| 1 | 3 | 33% | 33% | low | False |
| 2 | 1 | 0% | 0% | medium | True |
| 3 | 1 | 0% | 0% | normal | True |
| 4+ | 1 | 0% | 0% | normal | True |

`data_sufficiency`/`is_strong_recommendation_allowed`はusable_history_countのみに依存するため、v0.1・v0.2で共通の値になる(Recommender自体は変更していないため)。

## Multi-performance比較(performance_countバケット別)

| bucket | 件数 | coverage v0.1(平均) | coverage v0.2(平均) | violation率 v0.1 | violation率 v0.2 |
|---|---:|---:|---:|---:|---:|
| 5-8 | 1 | 0.657 | 0.785 | 100% | 100% |
| 9-15 | 1 | N/A | N/A | N/A | N/A |
| 16-20 | 1 | 0.345 | 0.423 | 100% | 100% |
| 21+ | 3 | 0.523 | 0.646 | 100% | 100% |

## データ品質に関する注意

- モデル係数(rule_v0.1)は本比較のために一切変更していない。rule_v0.2はrule_v0.1のestimate_demand()を内部で再利用しており、n=1では両者は完全に一致する。
- サンプル数が非常に少ないため(実在団体3団体、評価済みtarget数6件)、本比較は「確定的な優劣判定」ではなく「観測された傾向」として扱うこと。
