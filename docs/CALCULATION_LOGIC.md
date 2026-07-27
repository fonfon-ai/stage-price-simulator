# CALCULATION_LOGIC.md — 計算ロジックと根拠

すべての係数はテンプレート/定数として `backend/app/calculation/constants.py` に定義し、
`explanation` オブジェクトとして各補正要因をユーザーに提示する（説明可能性、SPEC.md 5章）。

## 1. 全体パイプライン

```
past_performance_sales[] --(censored補正)--> corrected_attendance[]
                          --(指数減衰加重平均)--> base_attendance_power
base_attendance_power × 各種補正係数 --> expected_demand_per_performance
expected_demand_per_performance --(公演回数の逓減モデル)--> total_expected_demand
total_expected_demand, capacity --> PerformanceSimulator --> sold / occupancy / revenue / profit
全シナリオ --> Recommender --> 満席重視/売上重視/利益重視/バランス価格 + Venue Fit
```

`DemandEstimator`（基礎集客力〜expected_demand_per_performanceまで）と
`PerformanceSimulator`（capacity制約・売上・利益の計算）を明確に分離する（`ARCHITECTURE.md`）。

## 2. Censored Data 補正（完売公演の真の需要推定）

完売公演の `tickets_sold` は真の需要の下限に過ぎない。以下の補正係数を乗じる。

```
correction_factor = 1.05 + min(0.15, days_before_sold_out * 0.01)   # 上限1.20
corrected_attendance = tickets_sold * correction_factor   (sold_out = True の場合)
corrected_attendance = tickets_sold                       (sold_out = False の場合)
```

根拠：
- 完売のみの場合、最低限のバッファとして+5%を見込む（当日券消化や機会損失の存在を仮定）。
- 完売までの日数が早いほど、機会損失（買えなかった潜在顧客）が大きいと仮定し、
  1日あたり+1%を加算、ただし上限は+20%（無根拠な過大推定を避けるため）。
- これは厳密な統計モデルではなく、MVPにおける保守的な簡易補正である。将来的には
  問い合わせ数・キャンセル待ち数等の追加データがあればより精緻化できる（`ML_PLAN.md`）。

## 3. 基礎集客力（Base Attendance Power）

過去公演を開催日の新しい順に並べ、指数減衰で加重平均する。

```
per_performance_attendance_i = corrected_attendance_i / num_performances_i
weight_i = decay ** i   (i=0が最新, decay=0.6 がデフォルト)
base_attendance_power = Σ(weight_i * per_performance_attendance_i) / Σ(weight_i)
```

`decay=0.6` は仕様で示された「直近50% / 2公演前30% / 3公演前20%」に近似する値として採用した
（0.6の等比数列を正規化すると概ね 51% / 31% / 18%）。4公演以上でも同じ式でそのまま一般化される。

## 4. 価格補正（Price Factor）— 内生性を排除するルールベース

**重要な設計判断**：過去データにおいて「高価格公演ほど高動員」という相関が見られても、
これは人気団体だから値上げできたという逆方向の因果（内生性）である可能性が高い。
したがって価格弾力性を過去データから回帰学習することはせず、
「基準価格からの乖離率に応じて需要が単調に減少する」というルールを固定で与える。

```
baseline_price = 過去公演の加重平均価格（base_attendance_powerと同じ重みで算出）
relative_change = (price - baseline_price) / baseline_price
price_factor = exp(-ELASTICITY * relative_change)   # ELASTICITY = 0.9 (default)
price_factor = clip(price_factor, 0.4, 1.3)
```

- `relative_change > 0`（値上げ）→ `price_factor < 1`（需要は必ず減少方向）。
- `relative_change < 0`（値下げ）→ `price_factor > 1` だが上限1.3でクリップ
  （値下げだけで需要が青天井に増えるという非現実的な推定を避ける）。
- `ELASTICITY` はチューニング可能な定数であり、業界弾力性の実データが得られ次第見直す。

## 5. その他の乗算補正

| 補正 | 条件 | 係数 |
|---|---|---|
| 平日/土日祝 | 土日祝 | ×1.08 |
| 昼/夜 | 夜公演 | ×1.05 |
| 新作/再演 | 新作 | ×1.05（新規性による集客） |
| 希少性 | low/mid/high | ×1.00 / ×1.05 / ×1.12 |
| ゲスト有無 | あり | ×1.07 |
| 特別公演 | 該当 | ×1.10 |
| 立地補正 | `location_rating`(1-5), `walk_minutes` | `clip(0.90 + 0.02*(rating-3) - 0.004*walk_minutes, 0.85, 1.15)` |
| 会場ブランド補正 | `brand_rating`(1-5) | `clip(0.95 + 0.02*(rating-3), 0.90, 1.15)` |

すべて根拠のある固定値であり、係数が0.85〜1.15程度に収まるよう意図的にクリップしている
（単一の補正でシナリオが極端化しないようにするため）。

## 6. SNS補正（補助情報。過大評価しない）

```
weighted_followers = x*1.0 + instagram*1.0 + youtube*1.2 + other*0.5
sns_score = log1p(weighted_followers)
sns_factor = 1 + min(0.05, 0.006 * sns_score)   # 最大+5%でキャップ
```

- 対数スケールにより、フォロワー数の桁が増えても効果は緩やかにしか増えない。
- 上限を+5%に固定することで「フォロワーが多いから動員できる」という単純判断を防止する
  （SPEC.md 最重要原則1）。SNSのみを理由に大規模会場を推奨することもない。

## 7. 公演回数の逓減モデル（Audience Pool Diminishing Returns）

同一公演を複数回開催する場合、観客プールは重複するため単純な線形加算（k倍）にはならない。

```
total_expected_demand = expected_demand_per_performance * (num_performances ** POOL_EXPONENT)
POOL_EXPONENT = 0.85  # デフォルト
```

`POOL_EXPONENT < 1` により、公演回数を増やすほど1公演あたりの需要は逓減する
（同一地域・同一期間で観客を奪い合うため）。シミュレーション上は
`total_expected_demand` を `num_performances` で均等按分して1公演あたり需要とする。

## 8. シミュレーション（PerformanceSimulator）

```
available_seats = capacity * num_performances
expected_sold = min(available_seats, total_expected_demand)
occupancy_rate = expected_sold / available_seats
revenue = expected_sold * price
profit = revenue - venue_cost * num_performances   # 会場費は1公演あたりの想定
```

`expected_sold` は必ず `available_seats` 以下（キャパ上限制御、Invariant Test対象）。

## 9. 価格探索

`price_min` 〜 `price_max` を **100円刻み** で全探索し、各価格・各会場・各公演回数候補について
上記シミュレーションを実行してシナリオ表を生成する。

## 10. 推奨価格（4種類 + バランス）

- **満席重視価格**：`occupancy_rate >= 0.90` を満たす価格の中で最も高い価格
  （満たすものが無ければ `occupancy_rate` 最大の価格）。
- **売上重視価格**：`price * expected_sold` を最大化する価格。
- **利益重視価格**：`profit` を最大化する価格。
- **バランス価格**：以下のスコアを最大化する価格・会場・公演回数の組み合わせ。

```
score = 0.30 * norm(occupancy_closeness)   # 目標帯[85%,97%]への近さ、外れるほど減点
      + 0.30 * norm(revenue)
      + 0.30 * norm(profit)
      - 0.10 * discount_penalty            # baseline_priceから大きく値下げした場合のペナルティ
```

正規化 `norm()` はシナリオ集合内の min-max 正規化。極端な安売り解や極端な過密解を
`occupancy_closeness` と `discount_penalty` により回避する（SPEC.md 10章「極端な解を避ける」）。

推奨価格帯は、バランス価格のスコアに対し95%以上のスコアを持つ価格帯の最小〜最大として算出する。

## 11. Venue Fit 判定

バランス価格・推奨公演回数における `occupancy_rate` を用いて判定する（テンプレート文生成、LLM不使用）。

| occupancy_rate | 判定 |
|---|---|
| >= 1.00（需要が上回る） | 小さすぎる |
| 0.75 〜 1.00 | 適切 |
| 0.55 〜 0.75 | やや大きい |
| < 0.55 | 大きすぎる（リスク警告テンプレートを表示） |

例：「この会場では予想稼働率が58%となり、現在の集客実績に対してやや大型です。」

## 12. 説明可能性ログ

`DemandEstimator.estimate_demand()` は最終値だけでなく、各補正係数を
`{factor_name, multiplier, description}` のリストとして返す。フロントエンドは
これをそのまま「なぜこの結果になったか」セクションに表示する（生成はテンプレート文字列、LLM不使用）。
