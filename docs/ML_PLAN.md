# ML_PLAN.md — 将来のML移行計画（MVPでは未実装）

## 予測対象の再定義

MLが予測するのは「適正価格」ではなく、**「その条件における潜在需要（真の需要の推定値）」**である。
価格・会場・公演回数の意思決定は、潜在需要をもとに `PerformanceSimulator` / `Recommender` が
（MVPと同じロジックで）行う。`DemandEstimator` インターフェースの実装を差し替えるだけでよい設計
（`ARCHITECTURE.md`）。

## Baseline（必須比較対象）

MLモデルは以下のBaselineを上回った場合にのみ採用する。

- **Baseline A**：前回公演動員（直近1公演の実績のみ）
- **Baseline B**：直近3公演の単純平均
- **Baseline C**：直近実績＋MVPの簡易補正（= 現行 `RuleBasedDemandEstimator` そのもの）

## 候補モデル

Linear Regression → Ridge → Random Forest → LightGBM → XGBoost の順に複雑化。
データ量が少ない初期段階では正則化線形モデルから開始し、データが十分に蓄積されてから
非線形モデル（Random Forest / GBDT系）を検討する。

## 評価指標

### 標準指標
- MAE / RMSE（動員数の予測誤差）
- 稼働率誤差（occupancy_rateのMAE）
- 売上誤差（revenue予測のMAE）

### サービス固有指標
- **Venue Fit Accuracy**：予測Venue Fit区分（小さすぎる/適切/やや大きい/大きすぎる）と
  実績Venue Fit区分の一致率
- **Price Safety**：推奨価格帯の外側で実績が発生した割合（推奨レンジの安全性）
- **Revenue Regret**：`(理論上の最良シナリオ利益 - 推奨シナリオの実績利益) / 理論上の最良シナリオ利益`
  として定義し、推奨が実績に対してどれだけ機会損失を生んだかを測る

## 検証方法

- **Time-based validation を基本とする**：過去→未来の時系列分割。ランダムなtrain/test splitは
  「未来のデータで過去を予測する」リークを生むため使用しない。
- **同一団体のリーク防止**：同じ団体の公演がtrainとtestの両方に混在しないよう、団体単位で
  train/testを分割するモード（Group-based split）も別途評価する。
- **未知団体（コールドスタート）テスト**：学習データに存在しない団体に対する予測精度は
  別テストセットとして分離評価する（SNS等の補助情報のみで推定する現実的なシナリオ）。

## MVPで導入しないもの

- LLM/生成AIによる需要予測・価格提案（`SPEC.md` 非機能要件）
- scikit-learn等MLパッケージへの強依存（インターフェースのみ用意し、実装は将来追加）

## 移行ステップ（将来）

1. `actual_results` テーブルに十分な実績データが蓄積される
2. `MLDemandEstimator(DemandEstimator)` を実装し、`DemandFeatures -> DemandEstimate` の
   scikit-learn互換インターフェースに準拠させる
3. Baseline A/B/Cと比較し、全指標で明確に上回った場合のみ本番導入
4. `simulation_runs.model_version` にモデルバージョンを記録し、A/Bで併存運用可能にする
