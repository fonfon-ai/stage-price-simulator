# TEST_PLAN.md

## Unit Test（`backend/tests/unit/`）
- 売上計算（revenue = expected_sold * price）
- 利益計算（profit = revenue - venue_cost * num_performances）
- キャパ上限制御（expected_sold は available_seats を超えない）
- 価格探索（100円刻みで price_min〜price_max を過不足なく列挙）
- 補正値（各補正係数が単体で仕様通りの倍率になるか）
- 基礎需要（指数減衰加重平均、censored補正込み）
- Venue Fit 判定（occupancy_rate の閾値境界）

## Invariant Test（`backend/tests/invariant/`）
SPEC.md 15章の常識的制約：
1. 同条件で価格を大幅に上げても需要（demand）は増えない（単調非増加）
2. 予測販売数は販売可能席数を超えない
3. 会場費増加だけでは利益は増えない（むしろ減る）
4. 同じ価格ならキャパを増やしても基礎需要（demand、capacity適用前）自体は増えない
5. SNSフォロワーを10倍にしても動員（sns_factor適用後の需要）は10倍にならない
   （+5%キャップの検証）

各不変条件はHypothesis等のランダム入力ではなく、代表値の組合せによるパラメトリックテストで検証する
（MVPでは決定論的ロジックのため、境界値・代表値のテストで十分にカバー可能）。

## Scenario Test（`backend/tests/scenario/`）
50ケース以上。以下の軸の直積からサンプリング・代表選定する：
- 団体属性: 無名劇団 / 若手劇団 / 人気劇団 / 若手コント / 人気コントユニット
- キャパ: 50 / 100 / 200 / 300 / 500
- 曜日: 平日 / 土日
- 価格帯: 低価格 / 高価格
- 完売パターン: 早期完売 / 長期販売でも未完売 / 完売なし

チェック項目（各シナリオ共通の非自然性チェック）：
- occupancy_rate が [0, 1] の範囲に収まっている
- 無名劇団に対して極端に高い価格・巨大会場が「バランス価格」として推奨されない
- 人気劇団に対して不当に低い価格が推奨されない（過度な値下げ回避スコアの検証）
- Venue Fitが「大きすぎる」場合にリスク警告文が生成される
- 全シナリオでexplanationが空でないこと（説明可能性の担保）

## Frontend Test（`frontend/`, Vitest + Testing Library）
- ステップウィザードの入力→次ステップ遷移のバリデーション
- 結果ダッシュボードが API レスポンスを正しく描画する（価格帯・シナリオ表・グラフ・Venue Fit・免責文言）
- API失敗時のエラーハンドリング表示

## 実行コマンド
```
cd backend && pytest -q
cd frontend && npm run test
```
