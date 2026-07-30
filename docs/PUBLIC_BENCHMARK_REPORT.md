# PUBLIC_BENCHMARK_REPORT.md

External Benchmark / Historical Backtest の結果報告。公開情報から収集した実在公演データに対し、Production側のルールモデルがどのような推奨を出すかを測定したものであり、モデルの係数は一切調整していない。

- **model_version**: `rule_v0.1`(固定・本フェーズ中は変更なし)
- **使用団体数(実在データのみ)**: 4
- **使用公演数(実在データ)**: 21
- **is_synthetic=true(架空・動作確認用)の行数**: 2(以下の統計からは除外)
- **拒否された公演数(validation error)**: 0
- **データ取得期間(run_start_dateの範囲、実在データ)**: 2018-08-01 〜 2026-05-26
- **データ欠損率(主要な補助特徴量ベース、実在データ)**: 96.8%
- **一次情報(confidence=A)比率(実在データ)**: 90.5%
- **Backtest評価対象(実在データ)**: 6件 / **スキップ(実在データ)**: 11件
- **特殊条件(COVID等)により標準backtestから除外**: 4件

## Benchmark Unit Bug(履歴記録・恒久保存)

**何が間違っていたか**: `benchmarks/scripts/model_adapter.py` の `_derive_tickets_sold()` が、`sold_out_status=all_sold_out` かつ `observed_attendance` 不明の履歴に対し、`venue_capacity`(1公演あたりの客席数)を そのまま `PastPerformance.tickets_sold`(Production側の契約では「run全体・全performance_count回分の合計販売枚数」)へ代入していた。さらに `benchmarks/scripts/metrics.py` の `recommended_capacity_low/high` が、興行全体(run全体)単位の `expected_demand` を `num_performances` で割り戻さずにそのまま `actual_venue_capacity`(1公演あたり単位)と並べて報告していた。

**なぜ発生したか**: Production側(`docs/DATA_MODEL.md`、`demand_estimator.py`)は `tickets_sold` を一貫して「run全体合計」として扱う契約になっているが、Benchmark側のスキーマ(`benchmarks/schema/models.py`)に `venue_capacity`・`observed_attendance`・`performance_count` の単位契約が明記されておらず、adapter実装時に「1公演あたりのcapacityを完売の下限としてそのまま使う」という誤った実装が入り込んだ。

**どの指標に影響したか**: `predicted_demand_at_actual_price`、`balanced_price`、`price_gap`/`percentage_price_gap`、`sold_out_lower_bound_violation`、`venue_fit_at_actual_price`、`recommended_capacity_low/high`。詳細は `docs/DEMAND_SEMANTICS_AUDIT.md` を参照。

**修正内容**:
1. `_derive_tickets_sold()`: `venue_capacity` → `venue_capacity × performance_count`(performance_count不明の場合は引き続き推測せず除外)。
2. `recommended_capacity_low/high`: Production側の `estimate_demand()` を `num_performances=1` で再呼び出しし(独自の変換式を新設せず既存ロジックを再利用)、1公演あたり単位に揃えてから算出するよう変更。
3. schemaのdocstring・`benchmarks/README.md` に各フィールドの単位契約を明記。

**修正前後の実測値(シソンヌ、2025-07-27時点のデータセットに対する実行)**:

| target年 | 行 | actual price | balanced BEFORE | balanced AFTER | predicted demand BEFORE | predicted demand AFTER | lower-bound violation BEFORE/AFTER | Venue Fit BEFORE/AFTER |
|---|---|---:|---:|---:|---:|---:|---|---|
| 2022 | REAL-0005 | 8,000円 | 14,400円 | 14,400円 | 152.3 | 2,131.7 | True / True | too_large / too_large |
| 2023 | REAL-0006 | 8,000円 | 7,600円 | 7,100円 | 261.9 | 3,978.0 | True / True | too_large / too_large |
| 2024 | REAL-0007 | 8,000円 | 8,200円 | 7,500円 | 243.9 | 4,312.4 | True / True | too_large / too_large |
| 2025 | REAL-0008 | 8,000円 | 8,500円 | 7,700円 | 242.9 | 4,631.2 | True / True | too_large / too_large |

**修正の効果**: predicted demandは修正により約14〜19倍に増加した(REAL-0002由来の`386`が`386×14=5,404`相当に是正されたため、後続の全targetへ連鎖的に反映)。一方、`sold_out_lower_bound_violation`は修正後も4件全てTrueのまま、`Venue Fit`も4件全てtoo_largeのままだった。**これは単位を揃えた上でなお観測された結果であり、以後はBenchmarkバグではなくrule_v0.1本体(特にPOOL_EXPONENTによる観客プール逓減の仮定)の挙動として評価対象とする。** 2022年(REAL-0005)のbalanced_priceが実売の+80%になる問題は、履歴がREAL-0002(2019)1件のみで薄いという条件下では修正後も解消しなかった(価格探索レンジの上限で頭打ちになっている)。2023年以降は履歴が2件以上に増えるにつれ、balanced_priceが実売価格に対し-11.25%→-6.25%→-3.75%と収束方向に推移している(修正前は+80%→-5.0%→+2.5%→+6.25%で符号が安定しない推移だった)。

## 合成データ(is_synthetic=true)の動作確認結果 — 参考情報

以下はパイプライン自体の動作確認用の架空データ(`SYN-`プレフィックス)の結果であり、**実在公演の統計には一切含めていない**。

- SYN-0001: actual=3500円 balanced=3600円 (price_gap=100円, 2.9%), venue_fit=too_large, sold_out_lower_bound_violation=True
- SYN-0002: skipped (no_usable_history)

## Actual Price と Recommended Price の差(実在データのみ)

注意: `actual_ticket_price` は「最適価格の正解ラベル」ではなく、あくまで比較対象の実績値である。

- price_gap(balanced_price - actual_price) 平均: 633円
- price_gap 中央値: -400円
- percentage_price_gap 平均: 6.8%
- percentage_price_gap 中央値: -5.0%

## Sold-out Lower-bound Violation(実在データ)

- 完売公演のうち lower-bound 評価が可能だった件数: 5
- lower-bound違反件数(モデル予測 < 実際の販売可能席数): 5

違反したケース:
- REAL-0005 (シソンヌ / シソンヌライブ[11]): predicted=2131.7
- REAL-0006 (シソンヌ / シソンヌライブ[12]): predicted=3978.0
- REAL-0007 (シソンヌ / シソンヌライブ[13]): predicted=4312.4
- REAL-0008 (シソンヌ / シソンヌライブ[14]): predicted=4631.2
- REAL-0015 (かが屋 / かが屋の大カロ貝展3): predicted=2765.5

## Venue Fit の傾向(実売価格時点、実在データ)

- too_large: 5件
- slightly_large: 1件

## 団体別結果(実在データ)

| 団体 | 評価件数 | price_gap平均 | percentage_price_gap平均 |
|---|---:|---:|---:|
| かが屋 | 1 | 0円 | 0.0% |
| シソンヌ | 4 | 1175円 | 14.7% |
| 劇団チョコレートケーキ | 1 | -900円 | -18.0% |

## 特殊条件(COVID等)により標準backtestから除外した公演

notesにCOVID等の特殊事情が記載されていても自動判定はせず、`excluded_from_standard_backtest=true` が明示された行のみを対象・履歴の両方から除外している。

- REAL-0003 (シソンヌ / シソンヌライブ[09]): covid_era_capacity_uncertain
- REAL-0004 (シソンヌ / シソンヌライブ[10]): covid_era_capacity_uncertain
- REAL-0016 (劇団チョコレートケーキ / 無畏): covid_era_capacity_uncertain
- REAL-0017 (劇団チョコレートケーキ / 帰還不能点): covid_era_capacity_restriction

## スキップされたケース(実在データ、データ不足で評価不能だったもの)

- no_usable_history: 10件
- missing_target_venue_capacity: 1件

内訳:
- REAL-0001 (シソンヌ / シソンヌライブ[07]): no_usable_history
- REAL-0002 (シソンヌ / シソンヌライブ[08]): no_usable_history
- REAL-0009 (ザ・ギース / neu（ノイ）): no_usable_history
- REAL-0010 (ザ・ギース / Venti): no_usable_history
- REAL-0011 (ザ・ギース / foodie): no_usable_history
- REAL-0012 (かが屋 / 瀬戸内海のカロカロ貝屋): no_usable_history
- REAL-0013 (かが屋 / かが屋の大カロ貝展): no_usable_history
- REAL-0014 (かが屋 / かが屋の大カロ貝展2): no_usable_history
- REAL-0018 (劇団チョコレートケーキ / ブラウン管より愛をこめてー宇宙人と異邦人ー): no_usable_history
- P2-READY-GC-2023-MATSUMOTO (劇団チョコレートケーキ / 『ブラウン管より愛をこめて －宇宙人と異邦人－』松本公演): no_usable_history
- REAL-0019 (劇団チョコレートケーキ / 白き山): missing_target_venue_capacity

## モデルが明らかに不自然だったケース(実在データ)

- REAL-0005 (シソンヌ): actual=8000円 balanced=14400円 (gap=80.0%), lower_bound_violation=True
- REAL-0006 (シソンヌ): actual=8000円 balanced=7100円 (gap=-11.2%), lower_bound_violation=True
- REAL-0007 (シソンヌ): actual=8000円 balanced=7500円 (gap=-6.2%), lower_bound_violation=True
- REAL-0008 (シソンヌ): actual=8000円 balanced=7700円 (gap=-3.8%), lower_bound_violation=True
- REAL-0015 (かが屋): actual=4500円 balanced=4500円 (gap=0.0%), lower_bound_violation=True

## 主要な観察: 実在データがHistorical Backtestで評価不能になった理由

実在データ21件中10件が `no_usable_history` (履歴として使える過去公演がゼロ)でスキップされた。原因は rule_v0.1 の係数ではなく、`model_adapter.py` の censored data 処理方針にある:

- 過去公演をPastPerformanceとして使うには `tickets_sold` 相当の値が必要。これは (a) `observed_attendance` が既知、または (b) `sold_out_status=all_sold_out` かつ `venue_capacity` が既知、のいずれかでなければ導出できない(捏造しない方針のため)。
- 今回のバッチでは `sold_out_status=unknown` かつ `observed_attendance` 未記入の行が多く、同一団体の過去公演がすべてこの状態だと、対象公演に使える履歴がゼロになりHistorical Backtestが実行できない。
- これはモデルの推奨精度の問題ではなく、**公開情報から実売数・完売状況を確認できる公演がまだ少ない**というデータ収集側の制約である。今後のバッチでは、`observed_attendance`(reported_totalでも可)または`sold_out_status`+`venue_capacity`の組み合わせを優先的に収集すると、評価可能件数を増やせる見込み。

## データ品質に関する注意

- このレポートに含まれる数値は、公開情報の収集状況に強く依存する。件数が少ない場合の平均値・傾向は参考程度に留めること。
- `defaulted_fields` が付与された評価は、立地/ブランド評価・SNS・平日祝日等の補助特徴量が公開情報から取得できず、ニュートラルな既定値で代替されたことを意味する(`benchmarks/results/benchmark_results.csv` の該当列を参照)。
