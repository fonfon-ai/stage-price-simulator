# DEMAND_SEMANTICS_AUDIT.md

External Benchmark / Historical Backtest の結果を受け、Stage Price Simulator内部で
「需要」を表す値がどの単位(1公演あたり／興行全体／ユニーク顧客数／延べ販売可能枚数)を
指しているかをコードベース全体で追跡した監査記録である。

**本監査ではコードを一切変更していない。** `rule_v0.1`・27係数・
`DemandEstimator`・`PerformanceSimulator`・`Recommender`・`VenueFit`・
`benchmarks/`配下のコードはすべて監査対象読み取りのみで、変更は行っていない
(`git diff`相当の変更なしであることは本ドキュメント作成時点のコード読解のみで確認済み)。

---

## 0. 結論(先出し)

**判定: B に近いが、実質的には C(意味が混在している)。**

- **Production側(`backend/app/calculation/`)は一貫して「興行全体(公演期間全体)需要モデル」として設計・実装されている。** `DemandEstimate.total_expected_demand`、`ScenarioResult.expected_demand/expected_sold/available_seats/revenue/profit` は全て「対象公演の全`num_performances`回を合計した総量」の単位で統一されており、内部に矛盾はない。
- **しかしBenchmark側(`benchmarks/scripts/model_adapter.py`と`benchmarks/scripts/metrics.py`)に、この「興行全体」契約と食い違う実装が2箇所存在する。** これにより、Production側のロジック自体は無傷でも、Benchmarkが計算・報告する数値は単位が壊れた入力に基づいたものになっている。
- 具体的には、**「386 (per-performance capacity) を興行全体のtickets_soldとして渡している」ことが今回の異常値の主因**であり、Historical Backtest報告で言及された「386×14=5,404相当」という解釈は**Production側の正しい契約と一致するが、現在のコードはそれを実装していない**。

---

## 1. Current Semantics(現在の実装における各値の意味)

### demand（需要）

`DemandEstimate`には3種類の「需要」に相当する値がある。

| フィールド | 単位 | 定義場所 |
|---|---|---|
| `base_attendance_power` | **1公演あたり** 動員数(過去実績の加重平均) | `demand_estimator.py:61` |
| `expected_demand_per_performance` | **1公演あたり** 需要(各種補正適用後) | `demand_estimator.py:179` |
| `total_expected_demand` | **興行全体(全`num_performances`回の合計)** 需要 | `demand_estimator.py:180-182` |

`ScenarioResult.expected_demand`(`simulator.py:45`)は`total_expected_demand`をそのまま渡した値であり、
**「興行全体」単位**。Recommender・Benchmark側から見える「demand」は基本的にこの`ScenarioResult.expected_demand`
経由であり、**すべて興行全体単位**である(`expected_demand_per_performance`は`DemandEstimate`の
内部中間値であり、`ScenarioResult`や`Recommendation`には一切露出しない)。

### attendance（動員・past performanceの解釈）

`PastPerformance.tickets_sold`は、**その過去公演run全体(`num_performances`回分の合計)の販売枚数**として
解釈されている。根拠:

1. `docs/DATA_MODEL.md:50` は production 側の `past_performance_sales.tickets_sold` を
   「総販売枚数（全公演合計）」と明記している。
2. `demand_estimator.py:58-59` の実装がこれと整合する:
   ```python
   per_perf_attendance = [
       _corrected_attendance(p) / max(1, p.num_performances) for p in past_sorted
   ]
   ```
   `_corrected_attendance(p)`(= 補正後のtickets_sold)を`num_performances`で**割って**
   1公演あたり平均を算出している。割り算が成立するのは`tickets_sold`が
   **run全体の合計**である場合のみ。

つまり `PastPerformance.tickets_sold` の契約は明確に **「興行全体(run合計)」** である。

### capacity（キャパシティ）

`VenueCandidate.capacity`と`PastPerformance.capacity`はいずれも**1公演あたり(1回の上演における)座席数**。
根拠: `simulator.py:32` `available_seats = venue.capacity * num_performances` — 1公演あたりキャパに
公演回数を掛けて初めて「興行全体の延べ販売可能枚数」になる、という掛け算の構造がこれを裏付ける。

なお `PastPerformance.capacity` は `demand_estimator.py` のどの計算式からも参照されておらず
(grep済み、未使用フィールド)、Production側の需要計算には一切影響しない。

### performance_count（公演回数）

`num_performances`は2箇所で異なる役割を果たす。

1. **過去公演側**: `PastPerformance.num_performances` は「run全体合計」を「1公演あたり平均」へ
   変換するための**除数**としてのみ使われる(`demand_estimator.py:59`)。
2. **対象(target)側**: `DemandFeatures.num_performances` は、算出された1公演あたり需要
   (`expected_demand_per_performance`)を**興行全体需要へ引き伸ばす**ための`POOL_EXPONENT`乗の
   底として使われる(`demand_estimator.py:180-182`)。同時に`PerformanceSimulator`では
   `available_seats = capacity * num_performances` の乗数としても使われる(`simulator.py:32`)。

このように、`num_performances`は「割る(過去)」「累乗のベースにする(対象)」「掛ける(キャパ)」という
3通りの異なる使われ方をするが、いずれも**内部的には一貫して興行全体⇄1公演あたりの相互変換**として機能しており、
Production側単体では矛盾しない。

### demand pool（観客プール、`POOL_EXPONENT`の意味）

```
total_expected_demand = expected_demand_per_performance * (num_performances ** POOL_EXPONENT)
```

`POOL_EXPONENT = 0.85` は、「同一runの複数公演は同一の観客プールを奪い合う」という前提のもと、
公演回数を増やすほど**1公演あたりの実質需要が逓減する**ことを表す指数。`num_performances`回分を
単純に線形合算(×`num_performances`、すなわち`POOL_EXPONENT=1`相当)するのではなく、
`num_performances ** 0.85`(< `num_performances`)を掛けることで「延べ人数」ではなく
「観客の重複を考慮したうえでの興行全体需要」を表現している。

重要な点: **この値は「ユニーク顧客数」を厳密にモデル化したものではない。** 同一顧客が複数公演に
来場する可能性を「プールの逓減」という形でざっくり近似しているに過ぎず、`total_expected_demand`は
「ユニーク顧客数」でも「延べ来場数(単純合計)」でもない、**その中間の近似値としての興行全体需要**である。

### expected sales（期待販売数）

`ScenarioResult.expected_sold = min(available_seats, total_expected_demand)`(`simulator.py:33`)。
`available_seats`(興行全体の延べ販売可能枚数)と`total_expected_demand`(興行全体需要)は
**同一単位(興行全体)であることを前提に**min演算されている。ここは単位面で正しい。

---

## 2. Data Flow(段階ごとの単位変化)

```
[past performance] tickets_sold (run全体合計, censored)
        │  ÷ num_performances_i  (demand_estimator.py:58-59)
        ▼
per_performance_attendance_i  ……………………………………… 単位: 1公演あたり
        │  × weight_i (指数減衰加重平均)          (demand_estimator.py:61)
        ▼
base_attendance_power  ……………………………………………… 単位: 1公演あたり
        │  × price/weekday/evening/new_work/rarity/
        │    guest/special/location/brand/sns 補正
        ▼
expected_demand_per_performance  ………………………………… 単位: 1公演あたり
        │  × (num_performances ** POOL_EXPONENT)   (demand_estimator.py:180-182)
        ▼
total_expected_demand  …………………………………………………… 単位: 興行全体(全num_performances回合計)
        │
        ├──→ PerformanceSimulator
        │      available_seats = capacity × num_performances  … 単位: 興行全体
        │      expected_sold = min(available_seats, total_expected_demand) … 単位: 興行全体
        │      occupancy_rate = expected_sold / available_seats … 単位: 無次元(比率)
        │      revenue = expected_sold × price … 単位: 興行全体の売上
        │      profit = revenue − venue_cost × num_performances … 単位: 興行全体の利益
        │            ▼
        │      VenueFit.classify_venue_fit(occupancy_rate) … 入力は無次元比率、単位問題なし
        │
        └──→ Recommender (scenariosの選択のみ、単位変換なし)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ここからBenchmark側(production側コードではない)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[BenchmarkPerformance] observed_attendance (単位契約が schema上で未明記)
        │
        ▼ model_adapter._derive_tickets_sold()
    ケースA: observed_attendance が既知
        → そのまま PastPerformance.tickets_sold へ         … 単位: 契約上は「run全体合計」のはずだが
                                                                 schemaに明記がなくデータ入力者依存
    ケースB: observed_attendance 不明 かつ sold_out かつ capacity既知
        → venue_capacity (1公演あたり) を そのまま tickets_sold へ  … ★単位不一致(下記3章参照)
        │
        ▼
PastPerformance.tickets_sold  ……… ケースBでは実際には「1公演あたり」の値が
                                     「run全体合計」の位置に渡っている

        │ (以降はProduction側のDemandEstimatorへそのまま入る。Production側は
        │  受け取った値を無条件に「run全体合計」として扱う契約なので、
        │  ここで単位のズレがそのままモデルへ伝播する)
        ▼
[metrics.py] BenchmarkResult.recommended_capacity_low/high
    = rec.balance_scenario.expected_demand / {1.0, VENUE_FIT_GOOD_MIN}
    … expected_demand は「興行全体」単位のままで、num_performancesによる
      1公演あたりへの割り戻しをしていない  … ★単位不一致(下記3章参照)
    一方 actual_venue_capacity = target.venue_capacity は「1公演あたり」単位
    → 同じ結果行の中で単位の異なる2つの「capacity」が並んで報告されている
```

---

## 3. Inconsistencies(切り分け)

| # | 不整合内容 | 所在 | 詳細 |
|---|---|---|---|
| 1 | **`_derive_tickets_sold`のcensored fallbackが`venue_capacity`(1公演あたり)を`tickets_sold`(run全体合計であるべき)にそのまま代入している** | **Benchmark adapter側** (`benchmarks/scripts/model_adapter.py` `_derive_tickets_sold`, 約92-96行目) | Production側の契約(`docs/DATA_MODEL.md`, `demand_estimator.py`の`/ num_performances`)では`tickets_sold`は run全体合計でなければならない。しかし現在のコードは`sold_out=True かつ venue_capacity既知`の場合に`venue_capacity`をそのまま返しており、正しくは`venue_capacity * performance_count`であるべき。 |
| 2 | **`recommended_capacity_low/high`が興行全体単位の`expected_demand`から1公演あたり換算(÷num_performances)をせずに算出されている** | **Benchmark metrics側** (`benchmarks/scripts/metrics.py` `evaluate_pair`, capacity_low/high算出部) | `rec.balance_scenario.expected_demand`は興行全体需要。これを`num_performances`で割らずに`/1.0`や`/VENUE_FIT_GOOD_MIN`しているため、算出される「推奨capacity」は実質「興行全体の延べ人数ベースの見かけの席数」であり、1公演あたり単位の`actual_venue_capacity`と直接比較できる数値になっていない。 |
| 3 | **schema定義上、`observed_attendance`の単位契約(1公演あたりか、run全体合計か)が明文化されていない** | **Schema定義側** (`benchmarks/schema/models.py` `BenchmarkPerformance.observed_attendance`) | Production側の`docs/DATA_MODEL.md`は`tickets_sold`を「総販売枚数（全公演合計）」と明記しているが、Benchmark側の`observed_attendance`にはこの契約への参照・docstringがない。今回は実害が出ていない(observed_attendanceが既知の行は全てexact/reported_totalかつ単一解釈で矛盾は生じていない)が、将来的なデータ入力ミスの温床になり得る。 |
| 4 | Production側(`DemandEstimator`/`PerformanceSimulator`/`Recommender`/`VenueFit`)自体には単位不整合は見つからなかった | — (問題なし) | 1章・2章で確認した通り、内部の単位変換(1公演あたり⇔興行全体)は一貫している。 |

**#1と#2は独立した別々のバグである点に注意。** #1はモデルへの**入力データの単位**が壊れている問題、
#2はモデルの**出力の解釈・表示**の単位が壊れている問題。#1を仮に修正しても#2は残る。

---

## 4. Impact(今回評価された4件への影響)

対象: REAL-0005(2022) / REAL-0006(2023) / REAL-0007(2024) / REAL-0008(2025)。
いずれも history の起点として **REAL-0002(2019, `tickets_sold=386`)** を含んでいる
(REAL-0005は直接、REAL-0006以降はREAL-0005自身も含めた連鎖的な影響)。

| 結果項目 | 影響を受けるか | 理由 |
|---|---|---|
| **predicted demand at actual price** | **影響を受ける(過小評価)** | `base_attendance_power`の算出根拠にREAL-0002由来の`386`(本来`386×14=5,404`であるべき)が使われており、直接的に過小評価の原因になっている。REAL-0006以降はREAL-0005自身(その時点で既に歪んでいる)も履歴に含むため、歪みが連鎖・累積している。 |
| **balanced price** | **影響を受ける(特に2022年は深刻)** | 過小評価されたbase_attendance_powerにより、価格弾力性の基準点(baseline_price)や需要推定全体が歪み、特にREAL-0005(履歴1件のみ、歪みが薄まらない)で実売価格比+80%という極端な結果につながった可能性が高い。 |
| **sold-out lower-bound violation** | **判定ロジック自体は単位一貫しているが、入力が歪んでいるため「違反」の程度が誇張されている** | `expected_demand < available_seats`の比較(#4参照)は単位的に正しい。しかし`expected_demand`自体が#1の影響で過小評価されているため、violation=Trueという結論の方向性は恐らく妥当でも、predicted_demand(152.3等)の絶対値は実態よりかなり小さく表示されている可能性が高い。 |
| **Venue Fit(too_large)** | **影響を受ける** | occupancy_rateの算出も歪んだexpected_demandに依存するため、"too_large"判定の信頼性は本来より低い。稼働率が実態よりかなり過小に出ている可能性がある。 |
| **recommended_capacity_low/high** (ユーザー明示の4項目には無いが監査で発見) | **影響を受ける(#2の影響)** | 4件すべてでこの値が`actual_venue_capacity`(386)と桁の異なる単位で算出されており、そのままでは比較に使えない。 |

**結論**: 今回の4件の異常値(REAL-0005の+80%ギャップ等)は、**rule_v0.1自体の欠陥ではなく、
Benchmark adapterの#1(および#2)による入力・表示単位の誤りによって少なくとも部分的に説明できる。**
真の需要スケールで再計算した場合、これらの結果は大きく変わる可能性が高い(ただし本監査では
再計算・修正は行っていない)。

---

## 5. 質問への直接回答(1〜10)

1. **`RuleBasedDemandEstimator`が返すpredicted demandの意味**: `total_expected_demand`は
   興行全体(対象runの全`num_performances`回合計)の需要。`expected_demand_per_performance`は
   1公演あたりの需要で、これは外部に露出しない内部中間値。
2. **base attendance / base demandの意味**: `base_attendance_power`は1公演あたりの
   過去実績加重平均動員数。
3. **past performanceのattendanceの解釈**: `tickets_sold`はそのrun全体(合計`num_performances`回分)の
   合計販売枚数として解釈される(除算により1公演あたりへ変換される)。
4. **performance_countをどの段階で使用しているか**: (a)過去側で「run合計→1公演あたり」の除数、
   (b)対象側で「1公演あたり→興行全体」への`POOL_EXPONENT`乗の底、(c)Simulatorで
   「1公演あたりcapacity→興行全体capacity」の乗数、の3箇所。
5. **PerformanceSimulatorで複数公演需要をどう配分しているか**: 配分(按分)はしていない。
   `total_expected_demand`(興行全体)と`available_seats`(興行全体)を直接min演算するのみで、
   個々の公演への配分ロジックは実装されていない。
6. **POOL_EXPONENTの意味**: 観客プールの重複を考慮した、公演回数に対する需要の逓減指数
   (1章参照)。ユニーク顧客数の厳密なモデルではない。
7. **capacityとの比較単位**: `available_seats`(=capacity×num_performances、興行全体)と
   `total_expected_demand`(興行全体)は同一単位で比較されており、Production側は正しい。
8. **Venue Fitの比較単位**: `occupancy_rate = expected_sold / available_seats`という
   興行全体同士の無次元比率であり、Production側は正しい。ただし Benchmark側の
   `recommended_capacity_low/high`は#2の通り単位が壊れている。
9. **sold_out lower-bound violationの比較単位**: `expected_demand < available_seats`、
   両者とも興行全体単位で比較ロジック自体は正しい(#4参照)。ただし入力(#1)が歪んでいる。
10. **Benchmark adapterでobserved_attendanceをDemandEstimatorへ渡す際の単位**:
    `observed_attendance`が既知の場合はそのまま`tickets_sold`へ渡り、契約上は
    run全体合計として扱われる(実害は確認されていないが、schema上の明記がない=#3)。
    `observed_attendance`が不明でsold_out+capacity既知の場合、`venue_capacity`(1公演あたり)を
    そのまま`tickets_sold`(run全体合計であるべき)へ渡しており、**ここが本質的な単位不一致(#1)**。

---

## 6. シソンヌライブ[08]の具体的検証

> venue_capacity = 386, performance_count = 14, sold_out_status = all_sold_out
> 現在のBenchmark adapterは observed attendance lower bound = 386 として履歴へ渡している。
> 一方、Historical Backtest報告では 386 × 14 = 5,404 相当を興行全体の完売下限として解釈している。

**この2つの解釈は整合していない。** `386 × 14 = 5,404`という解釈が
**Production側の`tickets_sold`契約(run全体合計)と正しく一致する**。現在のコード
(`model_adapter.py`の`_derive_tickets_sold`)が実装しているのは前者(`386`をそのまま渡す)であり、
これは契約違反である。Historical Backtest報告書の文中の解釈(5,404)はコードの実際の挙動を
正しく言い当てたものではなく、**「本来あるべき正しい値」を指摘したものであり、現在のコードの
実装とは異なる**、という位置付けで理解するのが正確である。

---

## 7. 判定

**B に限りなく近いが、正確には C(意味が混在している)。**

- Production側の設計・実装だけを見れば **B(興行全体需要モデル)** で完全に一貫している。
- しかし実際に動いている「Stage Price Simulator + Benchmark基盤」全体で見ると、
  Benchmark adapterの1箇所(`_derive_tickets_sold`のsold-outフォールバック)が
  「1公演あたり」の値を「興行全体合計」の位置に混入させているため、
  **システム全体としては単位が混在している(C)** と判定する。

---

## 8. Historical Backtestを再実行する前に必要な最小修正案(未適用・提案のみ)

**以下は提案であり、本監査フェーズでは一切適用していない。** ユーザーの承認後に別フェーズで
実施することを想定する。

1. **`benchmarks/scripts/model_adapter.py::_derive_tickets_sold`** の
   `sold_out and venue_capacity is not None` 分岐を
   `venue_capacity * case.performance_count`(run全体合計としての下限)を返すように修正する。
   ただし`case.performance_count`がNoneの場合はこの分岐自体を使えない(既存の
   `performance_count is None → 履歴除外`ロジックにより、このケースは既に除外されている想定)。
2. **`benchmarks/scripts/metrics.py`** の`recommended_capacity_low/high`算出を
   `rec.balance_scenario.expected_demand / rec.balance_scenario.num_performances` を
   基準にしてから`/1.0`・`/VENUE_FIT_GOOD_MIN`する(1公演あたり単位に揃えてから
   `actual_venue_capacity`と比較可能にする)。
3. **`benchmarks/schema/models.py`** の`observed_attendance`フィールドに、
   「run全体合計(全performance_count分の合計)であること」を明記するdocstringを追加する。
4. 上記1〜3の修正後、**既存のbenchmarksテスト(43件)に加えて**、
   「`performance_count > 1`のsold-outフォールバックが`capacity × performance_count`を
   返すこと」を検証する回帰テストを追加してから、Historical Backtestを再実行することを推奨する。
5. 修正1を適用した場合、REAL-0002(2019)・REAL-0005〜0008(2022-2025)すべての
   `tickets_sold`実効値が大きく変わるため、**再実行結果は今回のレポートとは大きく異なる数値になる
   ことが予想される**。これは「修正が正しく効いている」ことの確認材料になる。
