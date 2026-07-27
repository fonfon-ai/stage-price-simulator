# RULE_V0_2_DESIGN.md

v0.1検証フェーズの結論に基づき、rule_v0.2を設計する。**数値を実売価格やシソンヌのcoverage比に
近づけるための係数調整ではなく、構造的に必要と判断した変更のみ**を行う。

rule_v0.1(`backend/app/calculation/constants.py`の27係数、`RuleBasedDemandEstimator`、
`PerformanceSimulator`、`Recommender`、`VenueFit`)は**一切変更していない**。
`backend/tests/unit/test_model_snapshot.py`で27係数の完全一致を継続的に保証する。

---

## PHASE 1: 既存実在データの再確認

既存の`benchmarks/data/public_performances.csv`(22行、source provenance付き)を
`load_dataset()`で再検証した。validation error 0件。今回のセッションでは新規の
Web一次情報調査は実施していない(スコープが既に大きいフェーズのため優先度を判断し見送った)。
既存データセットの再検証のみで以下を確認している。

- シソンヌ: REAL-0001〜0011のうちREAL-0005/0006/0007/0008の4件がusable history条件を満たしBacktest可能。
- かが屋: REAL-0012〜0015のうちREAL-0015の1件がBacktest可能(REAL-0014をusable historyとして使用)。
- ザ・ギース: REAL-0009〜0011は全件`observed_attendance`/`sold_out_status`由来のtickets_soldが
  導出できずusable historyにならず、評価可能なtargetは0件。
- 劇団チョコレートケーキ: REAL-0016〜0020のうちCOVID特殊条件2件を除く3件は
  `performance_count`欠損等によりusable historyにならず、評価可能なtargetは0件。

**Remaining Risk**: ザ・ギース・劇団チョコレートケーキの実データは今回拡充していない。
次フェーズで一次情報(公式サイト・チケット会社の完売告知等)を追加収集することを推奨する
(詳細はRemaining Risksを参照)。

---

## Cross-organization判定: performance_count と demand_coverage_ratio の関係

| 団体 | performance_count | demand_coverage_ratio |
|---|---:|---:|
| シソンヌ(平均, 4件) | 約20.7 | 約0.478 |
| かが屋(1件) | 8 | 0.657 |

**判定: 傍証あり(確定ではない)。**

公演回数が多い(シソンヌ、約16〜22公演)ほどcoverage比が低く(0.478平均)、
公演回数が少ない(かが屋、8公演)ほどcoverage比が高い(0.657)という、
「公演回数が多いほど総需要を過小評価する」という仮説(H1)と**方向性が一致する**
2団体間の比較が得られた。ただし団体数が2、かが屋のサンプルは1件のみであり、
**団体固有の集客力の違い・会場規模の違い等の交絡要因を排除できていないため、
「確定」の水準には至っていない。**

---

## PHASE 2: rule_v0.1の問題の最終分類

### H1〜H4の判定

| 仮説 | 判定 | 根拠 |
|---|---|---|
| H1: 公演回数が多いほど総需要を過小評価する | **支持(構造上の問題として採用、A)** | POOL_EXPONENT=1.00(線形)でもシソンヌの完売下限を再現できず、かが屋(8公演, coverage 0.657)とシソンヌ(約21公演, coverage 0.478平均)の比較も方向性が一致。詳細はdocs/MODEL_STRUCTURE_DIAGNOSTIC.md参照。 |
| H2: 原因はPOOL_EXPONENTだけでなく1公演あたり基礎需要推定にもある | **部分的に支持(ただし今回は据え置き)** | POOL_EXPONENT=1.00でも需要が届かない事実はH2を支持するが、これは「実売価格が過去の基準価格より高い場合に価格弾力性が需要を抑制する」という v0.1既存機構の正常な帰結である可能性を排除できていない。1公演あたり需要推定式(base_attendance_power・価格弾力性)自体は27係数の一部であり、今回は変更しない。Remaining Riskとして記録する。 |
| H3: usable historyが1件のとき価格推奨が探索レンジ境界に張り付く | **支持(構造上の問題として採用、A)** | target条件固定のsynthetic diagnosticで直接再現済み(履歴1件のみ+80%、2件以降は±11%以内に収束)。 |
| H4: Balanced Recommendation Objective自体は需要推定誤差の影響を受けているだけ | **支持(現状維持、C)** | 目的関数の重み付け・ロジックは意図通りに動作しており、値下げ方向への挙動は上流の需要過小評価(H1)の影響を受けた結果である。Recommenderの数式自体を変更する必要性は認められない。 |

### 3項目の最終分類

| 項目 | 分類 | 対応方針 |
|---|---|---|
| 1. Multi-performance Demand Scaling | **A. 修正すべき構造問題** | POOL_EXPONENTの値を調整するのではなく、Accessibility GainとCannibalizationを別概念として構造分離する(下記参照)。 |
| 2. Thin History / Cold Start | **A. 修正すべき構造問題** | モデル式(DemandEstimator)のチューニングではなく、Recommender層に「Prediction Confidence / Data Sufficiency」というガードレール概念を追加する。価格の数値そのものはclampしない。 |
| 3. Balanced Recommendation Objective | **C. 現状維持** | Recommenderの目的関数・重みは変更しない。 |

---

## v0.2の変更内容

### 変更1: Multi-performance Demand Scalingの構造分離

**変更前(v0.1)**:
```
total_expected_demand = expected_demand_per_performance * (num_performances ** POOL_EXPONENT)
```
単一のPOOL_EXPONENTが「観客プールの重複(cannibalization)」と「本来考慮すべき到達可能顧客の
増加(accessibility)」の両方を暗黙に(かつaccessibilityは全く考慮せず)表現しようとしていた。

**変更後(v0.2)**:
```
total_expected_demand = expected_demand_per_performance
                        × accessibility_gain(n)
                        × cannibalization_multiplier(n)

accessibility_gain(n)      = 1 + ACCESSIBILITY_GAIN_MAX * (1 - n ** (-ACCESSIBILITY_GAIN_DECAY))
cannibalization_multiplier(n) = n ** CANNIBALIZATION_EXPONENT_V2
```

- `expected_demand_per_performance`は**v0.1の`RuleBasedDemandEstimator.estimate_demand()`を
  そのまま呼び出して取得する**(価格・曜日・新作/再演・希少性・ゲスト・特別公演・立地・
  会場ブランド・SNS補正・completed data補正・直近重視加重平均は一切複製・再チューニングしない)。
- `CANNIBALIZATION_EXPONENT_V2`はv0.1の`POOL_EXPONENT`(0.85)と**同一値をそのまま参照**する
  (区分: structural。値を変えて数字を合わせることを避けるため、実証データが無い現時点では
  意図的に据え置く)。
- `ACCESSIBILITY_GAIN_MAX = 0.30`、`ACCESSIBILITY_GAIN_DECAY = 0.5`は**新規追加する
  唯一の2つの仮定**(区分: heuristic)。n=1で効果ゼロ、nが増えるほど「日程の融通で
  行けるようになる」需要増加が最大+30%まで頭打ちで漸近する構造。

**Core Audience / Schedule Accessibility / Cannibalizationの対応関係**:

| 概念 | v0.2での対応 |
|---|---|
| Core Audience | `expected_demand_per_performance`(v0.1そのまま。固定ファン+価格弾力性等の需要) |
| Schedule Accessibility | `accessibility_gain(n)`(新規。日程選択肢の増加による追加需要、上限あり) |
| Cannibalization | `cannibalization_multiplier(n)`(v0.1のPOOL_EXPONENTをそのまま継承) |

n=1のとき`accessibility_gain(1)=1.0`かつ`cannibalization_multiplier(1)=1.0`となるため、
**単一公演のケースではv0.2はv0.1と完全に同一の結果を返す**(アンカーポイント保存、
回帰テストで保証済み)。

### 変更2: Prediction Confidence / Data Sufficiency

新規モジュール`backend/app/calculation/confidence.py`を追加。`DemandEstimator`/
`PerformanceSimulator`/`Recommender`とは独立したガードレール層であり、
**使える過去実績(usable history)の件数だけを入力として、価格推奨の信頼度を評価する**。

| usable_history_count | Data Sufficiency | 挙動 |
|---:|---|---|
| 0 | (評価不能。v0.1と同様に`ValueError`) | — |
| 1 | LOW | strong recommendation禁止。必ずwarningsを伴う。境界張り付き時は追加警告。 |
| 2 | MEDIUM | 中程度の信頼度として警告を付与。 |
| 3以上 | NORMAL | 通常推奨。境界張り付き時のみ情報を付与(無警告にはしない)。 |

**重要**: この層は価格の数値を一切変更しない(clampしない)。`is_strong_recommendation_allowed`
というbooleanと`warnings: list[str]`を提供するのみであり、UI/API側で「Prediction Confidence」
または「Data Sufficiency」として表示可能な内部構造を提供する(表示UIの実装は本フェーズの
スコープ外。内部データ構造の追加のみ)。

### 変更しなかったもの

- rule_v0.1の27係数・`RuleBasedDemandEstimator`・`PerformanceSimulator`・`Recommender`・
  `VenueFit`のロジックは一切変更していない。
- Balanced Recommendation Objective(occupancy/revenue/profitの重み付け)は変更しない(C判定)。
- 1公演あたり基礎需要推定式(価格弾力性・直近重視加重平均・completed data補正)は変更しない
  (H2は部分支持だが、修正の実証的根拠が不足しているため今回は据え置き、Remaining Riskとする)。
- 新しい「魔法の係数」は最小限(ACCESSIBILITY_GAIN_MAX・ACCESSIBILITY_GAIN_DECAYの2つのみ)に
  留めた。CANNIBALIZATION_EXPONENT_V2はv0.1の値をそのまま継承しており、新規係数ではない。

---

## 過学習防止についての設計判断

Accessibility Gainの2係数(0.30, 0.5)は、**シソンヌのdemand_coverage_ratioを1.0へ
近づけることを目的に選択していない。** 選定の考え方は以下の通り:

- n=22(シソンヌの最大値)でのaccessibility_gainは約1.236、n=8(かが屋)では約1.194。
  この程度の上乗せでもシソンヌのcoverage比(0.478)は依然1.0に遠く届かない
  (v0.2でも完売下限を完全には再現できない。下記PHASE 6の実測値を参照)。
  **意図的に「シソンヌのcoverageを1.0に合わせ込む」ような大きな係数は採用していない。**
- 係数はあくまで「日程の融通による追加需要は多くても+30%程度、10回前後で頭打ち」という
  一般的で保守的な仮定であり、シソンヌ・かが屋どちらのケースにも同一の関数形・同一の
  係数値を適用している(団体別のチューニングは一切行っていない)。
- Synthetic stress caseとして、performance_count=1000等の極端な値でもaccessibility_gainが
  有界であることを回帰テストで確認済み(`test_accessibility_gain_is_bounded`)。

---

## Remaining Risks(今後実データで検証すべき事項)

1. 1公演あたり基礎需要推定(H2の残課題): 価格弾力性・直近重視加重平均が、
   実売価格が過去実績より高いケースでどの程度妥当かは未検証。
2. Accessibility Gainの係数(0.30, 0.5)は非実証のheuristic。かが屋以外の中頻度公演団体
   (5〜15公演程度)のusable historyが増えた時点で再キャリブレーションが必要。
3. ザ・ギース・劇団チョコレートケーキの実データはusable historyが0件のままであり、
   H1の「複数公演モデル全般」への一般化はまだ2団体のみの傍証に留まる。
