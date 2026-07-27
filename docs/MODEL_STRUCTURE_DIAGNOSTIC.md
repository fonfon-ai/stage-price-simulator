# MODEL_STRUCTURE_DIAGNOSTIC.md

Historical Backtestの単位不整合修正(`docs/DEMAND_SEMANTICS_AUDIT.md`)後に観測された
rule_v0.1本体の3つの問題候補について、**係数・ロジックを一切変更せずに**構造診断を行った記録。

**重要**: 本診断では `rule_v0.1` の27係数・`DemandEstimator`/`PerformanceSimulator`/
`Recommender`/`VenueFit` のコードを一切変更していない。POOL_EXPONENTのwhat-if診断のみ
`app.calculation.constants.POOL_EXPONENT` を実行時に一時的にモンキーパッチし、各計算後に
必ず元の値(0.85)へ復元している(`backend/tests/unit/test_model_snapshot.py` で
診断実行後も係数が無変更であることを確認済み)。

再現方法:
```bash
cd (repo root)
backend/.venv/Scripts/python.exe -m benchmarks.scripts.diagnostics_model_structure
```

---

## 調査テーマ1: Multi-performance Demand Scaling(POOL_EXPONENT)

### POOL_EXPONENTが使われる式

`backend/app/calculation/demand_estimator.py`:

```python
expected_demand_per_performance = demand  # 1公演あたり(価格・曜日・SNS等の補正まで適用済み)
total_expected_demand = expected_demand_per_performance * (num_performances ** POOL_EXPONENT)
```

`POOL_EXPONENT = 0.85`(現状維持)。1公演あたり需要を`num_performances`回分の
「興行全体需要」へ引き伸ばす際、単純な線形合算(×`num_performances`)ではなく
`num_performances ** 0.85`(< `num_performances`)を掛けることで、同一runの複数公演が
観客プールを共有する(カニバリゼーション)という前提を表現している。

### performance_count別の需要変化(具体的数値)

診断条件: 過去実績が「386席(本多劇場相当)満席×14公演」の1点のみという、
シソンヌ2019年相当の`base_attendance_power`を使用(価格・曜日等の補正は中立)。

| n(公演回数) | pool_multiplier = n^0.85 | 興行全体需要 | 1公演あたり需要 | 満席時に必要な延べ席数(386×n) | 充足率 |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.000 | 338.8 | 338.8 | 386 | 87.78% |
| 2 | 1.803 | 610.7 | 305.4 | 772 | 79.11% |
| 5 | 3.928 | 1,330.8 | 266.2 | 1,930 | 68.95% |
| 10 | 7.079 | 2,398.7 | 239.9 | 3,860 | 62.14% |
| 14 | 9.423 | 3,193.0 | 228.1 | 5,404 | 59.08% |
| 16 | 10.556 | 3,576.7 | 223.5 | 6,176 | 57.91% |
| 21 | 13.301 | 4,506.8 | 214.6 | 8,106 | 55.60% |
| 22 | 13.838 | 4,688.6 | 213.1 | 8,492 | 55.21% |

### 1公演→22公演の総需要倍率

```
total_expected_demand(n=22) / total_expected_demand(n=1) = 22^0.85 / 1^0.85 = 13.838倍
```

線形モデル(カニバリゼーションなし)なら22倍になるはずが、**13.838倍(≒63%)** に
抑制されている。

### 1公演あたり需要の変化

n=1のとき338.8人/公演(基準値相当)だったものが、n=22では213.1人/公演まで低下する
(基準値の**62.9%**まで逓減)。つまりこのモデルは「公演回数を増やすほど、
1公演あたりに集まる客足は減っていく」という前提を明示的に持っている。

### カニバリゼーションの仮定度合い

`POOL_EXPONENT=0.85`は「観客プールの83.8%が公演間で共有されている」という強さの
仮定に相当する(n=22で充足率55.21%まで低下することから、22公演フルの独立需要が
あれば埋まるはずの席の半分弱しか埋まらない計算になる)。これは**かなり強いカニバリゼーション
仮定**であり、同一都市・同一劇場での高頻度リピート公演(本多劇場での14〜22公演等)には
特に強く効く。

### 「公演数増加による到達可能顧客増加」の考慮有無

**考慮されていない。** `RuleBasedDemandEstimator`のコードには、地理的リーチの拡大・
口コミによる新規顧客誘引・SNS等での認知拡大による観客プール自体の増加を表す項が
一切存在しない。`POOL_EXPONENT`は単一の指数として「重複だけ」をモデル化しており、
「公演を重ねることで新規顧客を追加獲得する」効果は明示的にゼロとして扱われている
(このモデルの意図的な単純化であり、バグではない。ただし本診断で「過小評価の主因の一つ」
であることは確認できた)。

### シソンヌのような高頻度公演で完売下限を構造上どこまで再現可能か

**構造上、再現できない可能性が高い。** 診断条件下で仮に全ての補正を最も需要に有利な
中立値にしても、n=14で充足率59.08%、n=22で55.21%までしか到達しない。
`POOL_EXPONENT`をさらに1.00(カニバリゼーションなし、線形合算)に引き上げても、
実際のシソンヌ2023〜2025データでは総需要が6,280〜7,363にとどまり、
必要な延べ席数(8,106〜8,492)にわずかに届かない(下記Sensitivity Diagnostic参照)。
つまり**POOL_EXPONENT単体の問題ではなく、1公演あたりの基礎需要推定自体も
完売という事実に対してやや過小**である可能性が高い。

---

## 調査テーマ2: Thin History / Cold Start(REAL-0005, 2022)

### 14,400円になる要因の分解

REAL-0005(2022年、シソンヌライブ[11])の利用可能履歴は **REAL-0002(2019年)の1件のみ**
(REAL-0001は`sold_out_status=unknown`のため引き続き使用不可)。

| 要素 | 値 | 説明 |
|---|---|---|
| base_attendance_power | 405.30人/公演 | REAL-0002(386×14=5,404人 / 14公演)がそのまま採用(履歴1件のため重み1.0) |
| baseline_price | 5,000円 | REAL-0002の価格がそのまま採用(履歴1件のため加重平均も1点のみ) |
| price_search_range | 4,000円〜14,400円 | 実売価格8,000円の0.5倍〜1.8倍(ベンチマーク側の便宜的な探索レンジ、係数ではない) |
| sold-out補正 | 適用済み(1.05倍) | REAL-0002の`days_before_sold_out`が不明のため最小補正(+5%)のみ |
| price_factor(価格弾力性) | 探索価格ごとに変動 | 基準価格5,000円に対し探索価格が上がるほど需要が単調減少(`math.exp(-0.9*相対変化)`) |

**なぜ14,400円(探索レンジ上限)になったか**: 稼働率(occupancy_rate)を計算条件下の
どの価格でも見ると、venue_capacity=386×16公演=6,176席に対し、価格を上げても
demandが6,176を大きく下回り続ける(最高価格14,400円でも稼働率23.69%)。
このため`occupancy_closeness`(目標稼働率85-97%への近さ)は**価格を上げても改善しない**
(むしろどんどん0.279近辺まで悪化していく)一方、`revenue_norm`・`profit_norm`は
価格が上がるほど単調に増加し続ける(稼働率が低いまま=需要が席数の天井に達しないため、
売上=価格×需要がそのまま伸び続ける)。結果、バランススコアは価格上限まで単調増加し、
**探索レンジの端で頭打ちになる**(診断ログの price=10100〜14400 で `occ_closeness` が
0.279で完全に横ばいのまま `revenue_norm`/`profit_norm` だけが増え続けているのが確認できる)。

### history件数を1→4に変えた場合の安定性(synthetic diagnostic)

target条件を固定(venue_capacity=386, performance_count=22, 実売価格8,000円、
価格探索レンジ4,000〜14,400円で統一)し、履歴件数のみを1〜4件に変化させた。

| history件数 | base_attendance_power | baseline_price | balanced_price | 実売比 |
|---:|---:|---:|---:|---:|
| 1件 | 405.30 | 5,000円 | **14,400円** | **+80.00%** |
| 2件 | 405.30 | 6,875円 | 7,100円 | -11.25% |
| 3件 | 405.30 | 7,449円 | 7,500円 | -6.25% |
| 4件 | 405.30 | 7,702円 | 7,700円 | -3.75% |

**明確な結論**: 履歴が1件しかない場合のみ、baseline_priceが極端に低い(5,000円、
直近の実売8,000円と乖離が大きい)ため、価格弾力性による需要抑制が効きすぎず
価格探索の上限まで単調にスコアが伸び続け、境界解(レンジ上限)に張り付く。
履歴が2件以上になった瞬間(baseline_priceが実売に近い6,875円まで上昇)、
balanced_priceは実売の±11%以内に収まり、3件・4件とさらに収束していく。
**「履歴1件」という特異点でのみ不安定化する、明確な閾値効果**であることが確認できた。

---

## 調査テーマ3: Recommendation Objective(balanced_priceの目的関数分解)

REAL-0006(2023, balanced=7,100円)・REAL-0007(2024, balanced=7,500円)・
REAL-0008(2025, balanced=7,700円)について、探索した全価格の
`occupancy_closeness` / `revenue_norm` / `profit_norm` とスコアを算出した
(`BALANCE_WEIGHT_DISCOUNT_PENALTY`項は3件とも`price >= baseline_price`のため
常に0で寄与なし)。

代表例(REAL-0006, 2023年): balanced_priceは7,100円だが、`revenue_price`/`profit_price`は
7,600円(実売8,000円により近い)。価格7,100円時点のスコア内訳:
`occ_closeness=0.650, revenue_norm=0.990, profit_norm=0.990` →
`score = 0.30×0.650 + 0.30×0.990 + 0.30×0.990 = 0.789`(僅差でこれが最大)。
7,600円時点では `occ_closeness=0.608`(低下)、`revenue_norm=1.000`(最大)だが、
`occ_closeness`の低下が`revenue_norm`のわずかな伸びを上回り、スコアはむしろ0.7825まで低下する。

**「Venue too_large判定→稼働率改善のため値下げ→balanced_price低下」という因果は、
実装上たしかに発生している。** `occupancy_closeness`関数は稼働率が目標帯(85-97%)を
下回るほど大きく減点する設計であり、`revenue_norm`/`profit_norm`は稼働率が
天井(100%)に達しない限り価格に対してほぼ単調増加するため、価格を上げるほど
稼働率がさらに下がる(=分母の稼働率で損をする)状況では、
`occupancy_closeness`の減点が`revenue_norm`/`profit_norm`の増分をわずかに上回る
価格帯でスコアが頭打ちになり、それが`balanced_price`として選ばれる。
実売価格(8,000円)より`revenue_price`/`profit_price`が高いのに対し、
`balanced_price`だけが一貫して低いのは、この`occupancy_closeness`項の影響が
明確に効いているためであり、偶然ではなく実装上再現性のある挙動である。

---

## Sensitivity Diagnostic: POOL_EXPONENT what-if(0.70〜1.00)

シソンヌ2023(REAL-0006)・2024(REAL-0007)・2025(REAL-0008)について、
実売価格8,000円時点のpredicted total demand・per-performance demand・
sold-out lower-bound violation・Venue Fit、およびbalanced_priceを
POOL_EXPONENT = 0.70, 0.75, 0.80, 0.85(現状), 0.90, 0.95, 1.00 で比較した。

### REAL-0006(2023年、21公演、available_seats=8,106)

| POOL_EXPONENT | predicted total demand | per-performance | violation | Venue Fit | balanced_price |
|---:|---:|---:|---|---|---:|
| 0.70 | 2,519.6 | 120.0 | True | too_large | 7,300円 |
| 0.75 | 2,933.9 | 139.7 | True | too_large | 7,200円 |
| 0.80 | 3,416.3 | 162.7 | True | too_large | 7,100円 |
| **0.85(現状)** | **3,978.0** | **189.4** | **True** | **too_large** | **7,100円** |
| 0.90 | 4,632.1 | 220.6 | True | slightly_large | 7,000円 |
| 0.95 | 5,393.8 | 256.8 | True | slightly_large | 6,900円 |
| 1.00(線形) | 6,280.6 | 299.1 | **True** | good | 7,300円 |

### REAL-0007(2024年、21公演、available_seats=8,106)

| POOL_EXPONENT | predicted total demand | per-performance | violation | Venue Fit | balanced_price |
|---:|---:|---:|---|---|---:|
| 0.70 | 2,731.4 | 130.1 | True | too_large | 7,800円 |
| 0.75 | 3,180.5 | 151.5 | True | too_large | 7,700円 |
| 0.80 | 3,703.4 | 176.4 | True | too_large | 7,600円 |
| **0.85(現状)** | **4,312.4** | **205.4** | **True** | **too_large** | **7,500円** |
| 0.90 | 5,021.4 | 239.1 | True | slightly_large | 7,500円 |
| 0.95 | 5,847.1 | 278.4 | True | slightly_large | 7,400円 |
| 1.00(線形) | 6,808.5 | 324.2 | **True** | good | 7,900円 |

### REAL-0008(2025年、22公演、available_seats=8,492)

| POOL_EXPONENT | predicted total demand | per-performance | violation | Venue Fit | balanced_price |
|---:|---:|---:|---|---|---:|
| 0.70 | 2,912.9 | 132.4 | True | too_large | 8,000円 |
| 0.75 | 3,399.8 | 154.5 | True | too_large | 7,900円 |
| 0.80 | 3,968.0 | 180.4 | True | too_large | 7,800円 |
| **0.85(現状)** | **4,631.2** | **210.5** | **True** | **too_large** | **7,700円** |
| 0.90 | 5,405.2 | 245.7 | True | slightly_large | 7,700円 |
| 0.95 | 6,308.6 | 286.8 | True | slightly_large | 7,700円 |
| 1.00(線形) | 7,363.0 | 334.7 | **True** | good | 8,100円 |

### 最も重要な発見

**POOL_EXPONENT=1.00(カニバリゼーション仮定を完全に撤廃し、単純な線形合算にした場合)でも、
3年分すべてで`sold_out_lower_bound_violation=True`のままだった。** これは、
「完売下限を再現できない」問題が **POOL_EXPONENT単体の設定値の問題ではない** ことを
明確に示している。POOL_EXPONENTを上げるほど`Venue Fit`が`too_large`→`slightly_large`→`good`
へ改善し、violationの絶対的な差(demand と available_seats の差)は縮まるが、
**1.00でもなお demand(6,281〜7,363) が available_seats(8,106〜8,492) にわずかに届かない。**
したがって、真因は「POOL_EXPONENTの値そのもの」というより、**1公演あたりの
基礎需要推定(base_attendance_power、価格弾力性適用後)が、実売価格8,000円という
条件下でも本来の満席水準(386人/公演)にわずかに届いていないこと**にある
(REAL-0006〜0008のper-performance demandは189〜325人/公演で、満席の386人には
POOL_EXPONENT=1.00でも届かない)。POOL_EXPONENTは「demand不足を悪化させる乗数」
ではあるが、単独の原因ではない。

---

## 各問題候補の判定

### 1. POOL_EXPONENT / multi-performance scaling

**A. 明確なモデル構造上の問題。**

- 数値的根拠: n=1→22で総需要13.838倍(線形なら22倍)、1公演あたり需要は基準の62.9%まで逓減。
- POOL_EXPONENTを1.00(線形)に戻してもviolationが解消しないため「POOL_EXPONENTの値の
  チューニング」だけでは解決しない構造的な問題である。カニバリゼーション項に加えて、
  「公演を重ねることで新規顧客を獲得する」という逆方向の効果が全くモデル化されておらず、
  高頻度・長期公演シリーズの需要を系統的に過小評価する設計になっている。

### 2. Thin-history instability

**A. 明確なモデル構造上の問題。**

- 履歴1件のときのみbalanced_priceが探索レンジ上限に張り付く境界解となり、
  実売価格比+80%という極端な推奨が発生することを、target条件を完全固定した
  synthetic diagnosticで再現・確認した。
- 履歴2件以上では速やかに収束する(±11%以内)ため、**「履歴件数が閾値(1件)を
  下回る場合にのみ発生する」という特定可能な構造的弱点**である。
  data不足で判断不能なのではなく、メカニズム(baseline_priceが単一の古い実売価格に
  引きずられ、価格弾力性による抑制が効きにくくなる)を具体的に特定できた。

### 3. Balanced recommendation objective

**C. 現状でも妥当な設計。**

- 「Venue too_large判定→稼働率改善のため値下げ→balanced_price低下」という因果は
  実装上たしかに発生しているが、これは`docs/CALCULATION_LOGIC.md`で明示的に意図された
  設計(稼働率・売上・利益を均等重視し、過度な値下げには別途ペナルティを課す)であり、
  バグではない。むしろ「需要が構造的に不足している(問題1により過小評価されている)会場に対し、
  値下げで稼働率を確保しようとする」のは、需要推定さえ正しければ合理的な振る舞いである。
- ただし、これは**問題1(需要過小評価)の影響を強く受けて発現する**ため、
  問題1が是正されれば`balanced_price`の値下げ方向への引っ張りも弱まる可能性が高い。
  目的関数の設計自体を「問題」として修正する必要性は現時点では低いと判断する。

---

## まとめ

| 問題候補 | 判定 | 根拠の強さ |
|---|---|---|
| POOL_EXPONENT / multi-performance scaling | **A(構造上の問題)** | 高(POOL_EXPONENT=1.00でも解消せず、per-performance需要自体の過小評価も確認) |
| Thin-history instability | **A(構造上の問題)** | 高(target固定のsynthetic diagnosticで閾値効果を直接再現) |
| Balanced recommendation objective | **C(現状の設計として妥当)** | 中(意図された設計通りに動作しており、問題1の副作用として現れているだけ) |

本診断では修正案の実装は行っていない。次フェーズでの修正検討時は、
POOL_EXPONENTの見直しだけでなく、**価格弾力性適用後の1公演あたり基礎需要が
なぜ実売価格8,000円条件下で満席水準(386人)にわずかに届かないのか**
(baseline_priceの算出方法、加重減衰、SNS上限キャップ等との相互作用)も
あわせて調査する必要がある。
