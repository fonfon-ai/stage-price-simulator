# 舞台公演 興行設計シミュレーター

演劇・コント・劇団・お笑いユニット等の主催者が、**チケット価格 × 会場キャパシティ × 公演回数** の
組み合わせを比較検討するための意思決定支援ツールです。

**このツールは「AIが適正価格を断定するサービス」ではありません。** 満席重視・売上重視・利益重視など、
主催者の目的によって「良い設計」は変わるという前提で、複数の観点からシナリオを提示します。

## 目次

- [Phase 1 Status](#phase-1-status)
- [Current Model Status](#current-model-status)
- [プロダクト概要](#プロダクト概要)
- [画面構成](#画面構成)
- [アーキテクチャ](#アーキテクチャ)
- [セットアップ](#セットアップ)
- [開発方法](#開発方法)
- [テスト方法](#テスト方法)
- [External Benchmark / Historical Backtest](#external-benchmark--historical-backtest)
- [計算ロジック概要](#計算ロジック概要)
- [将来のML移行方針](#将来のml移行方針)
- [セキュリティ](#セキュリティ)
- [免責事項](#免責事項)
- [Phase 2 TODO](#phase-2-todo)

---

## Phase 1 Status

**Stage Price Simulator Phase 1: COMPLETE**

Phase 1で完了した内容:

- Rule-based MVP実装(`RuleBasedDemandEstimator` / `PerformanceSimulator` / `Recommender` / `VenueFit`)
- Acceptance / Calibration完了([docs/CALIBRATION_REPORT.md](docs/CALIBRATION_REPORT.md))
- Historical Benchmark基盤構築([benchmarks/](benchmarks/))
- 実在公演Historical Backtest実施([docs/PUBLIC_BENCHMARK_REPORT.md](docs/PUBLIC_BENCHMARK_REPORT.md))
- Benchmark Unit Semantics監査・修正([docs/DEMAND_SEMANTICS_AUDIT.md](docs/DEMAND_SEMANTICS_AUDIT.md))
- Cross-organization Diagnostic実装([docs/CROSS_ORGANIZATION_DIAGNOSTIC.md](docs/CROSS_ORGANIZATION_DIAGNOSTIC.md))
- rule_v0.1構造診断([docs/MODEL_STRUCTURE_DIAGNOSTIC.md](docs/MODEL_STRUCTURE_DIAGNOSTIC.md))
- experimental rule_v0.2実装([docs/RULE_V0_2_DESIGN.md](docs/RULE_V0_2_DESIGN.md))
- v0.1 vs v0.2比較([docs/RULE_V0_2_EVALUATION.md](docs/RULE_V0_2_EVALUATION.md))
- Cold Start / Data Sufficiency Guardrail実装(`backend/app/calculation/confidence.py`)

現在のモデル選択:

- **Production**: `rule_v0.1`
- **Experimental**: `rule_v0.2`(データ不足のためProduction昇格しない)

## Current Model Status

`rule_v0.1` is the current production/default rule model. Its 27 coefficients are frozen and
covered by a regression snapshot test (`backend/tests/unit/test_model_snapshot.py`).

`rule_v0.2` is an **experimental** model that separates multi-performance demand into:

- Core Audience(1公演あたり基礎需要。v0.1の`RuleBasedDemandEstimator`をそのまま再利用)
- Accessibility Gain(公演回数増加による到達可能顧客の増加。v0.2で新規追加、heuristic)
- Cannibalization(観客プールの重複による逓減。v0.1のPOOL_EXPONENTをそのまま継承)

Historical benchmark results are directionally promising(実在2団体・評価済み5targetすべてで
demand_coverage_ratio・Venue Fitが改善方向)but the available real-world dataset is too small
to justify promoting v0.2 to the default model.

### Current Decision

**NOT ENOUGH DATA**

v0.2再評価条件(目安):

- 最低3団体以上
- 各団体2件以上のusable historical targets

ただし **Cold Start / Data Sufficiency Guardrail(LOW/MEDIUM/NORMAL)は、サンプル数に
依存せず論理的に正しい安全機構であるため、既に採用済み**。usable historyが1件のみの場合、
strong recommendationは禁止され、warningsを伴う低信頼度の結果として返される。

詳細は [docs/RULE_V0_2_EVALUATION.md](docs/RULE_V0_2_EVALUATION.md) を参照。

---

## プロダクト概要

入力（団体情報 / 過去公演実績 / 今回公演の条件 / 候補会場）をもとに、価格を100円刻みで探索し、
会場×公演回数×価格のシナリオを網羅的にシミュレーションします。単一の「正解」ではなく、

- 満席重視価格（目標稼働率90〜100%）
- 売上重視価格（売上最大化）
- 利益重視価格（会場費を考慮した利益最大化）
- バランス価格（稼働率・売上・利益・過度な値下げ回避を総合したスコア最大化）

の4つの推奨と、その根拠（説明可能性ログ）を提示します。詳細な設計判断は `docs/` 配下を参照してください。

- [docs/SPEC.md](docs/SPEC.md) — 要件仕様
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) — データモデル
- [docs/CALCULATION_LOGIC.md](docs/CALCULATION_LOGIC.md) — 計算ロジックと根拠
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 技術アーキテクチャ
- [docs/TEST_PLAN.md](docs/TEST_PLAN.md) — テスト計画
- [docs/ML_PLAN.md](docs/ML_PLAN.md) — 将来のML移行計画
- [docs/CALIBRATION_REPORT.md](docs/CALIBRATION_REPORT.md) — Acceptance/Calibrationフェーズ報告
  (E2E検証結果、100件超のCalibration Test Dataset、感度分析、係数の仮置き一覧、公開判定)

## 画面構成

ステップ形式のウィザードです。

1. STEP 1: 団体情報（団体名・ジャンル・活動年数・SNSフォロワー数）
2. STEP 2: 過去公演（1件以上、推奨3〜5件）
3. STEP 3: 今回の公演（開催条件・希望価格帯・公演回数候補）
4. STEP 4: 候補会場（複数登録可）
5. STEP 5: シミュレーション結果（推奨価格帯・シナリオ比較表・グラフ・Venue Fit・説明可能性・免責文言）

PC・スマホ両対応のレスポンシブレイアウトです。

## アーキテクチャ

```
frontend/   React + TypeScript + Vite（ステップウィザード + 結果ダッシュボード）
backend/
  app/
    calculation/   DemandEstimator(抽象) / RuleBasedDemandEstimator(MVP実装)
                   PerformanceSimulator / Recommender / VenueFit判定
    api/           FastAPIルーター
    models/        SQLAlchemy ORM
    schemas/       Pydantic 入出力スキーマ
  tests/           unit / invariant / scenario
```

- LLM（OpenAI/Claude/Gemini等）には一切接続していません。すべてdeterministicなルールベース計算です。
- 需要予測コンポーネント `DemandEstimator` のみを、将来 `MLDemandEstimator` に差し替え可能な設計にしています。
  詳細は [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) と [docs/ML_PLAN.md](docs/ML_PLAN.md) を参照してください。
- Next.js ではなく Vite+React を採用しています（理由は `docs/ARCHITECTURE.md` 参照）。

## セットアップ

### バックエンド

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows: .venv\Scripts\activate / mac・Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # 必要に応じて値を編集
uvicorn app.main:app --reload
```

デフォルトでは `http://localhost:8000` でAPIが起動し、開発用SQLite（`theater_pricing.db`）を使用します。

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` でアクセスできます。開発サーバーは `/api` へのリクエストを
`http://localhost:8000` にプロキシします（`vite.config.ts`）。

## 開発方法

- バックエンドの計算ロジックは `backend/app/calculation/` に集約しており、FastAPI/DBに依存しません。
  ロジックを変更する場合は `docs/CALCULATION_LOGIC.md` も併せて更新してください。
- 補正係数はすべて `backend/app/calculation/constants.py` に定数として定義しています。
  マジックナンバーを直接ロジック内に埋め込まないでください。
- 本番環境向けDBは `DATABASE_URL` 環境変数でPostgreSQL等に切替可能です（SQLAlchemy ORM経由）。

## テスト方法

```bash
# バックエンド: lint / 型チェック / テスト
cd backend
ruff check .
mypy app
pytest -q

# フロントエンド: lint / 型チェック / テスト / ビルド
cd frontend
npx eslint .
npx tsc -b --noEmit
npx vitest run
npm run build
```

テスト内容の詳細は [docs/TEST_PLAN.md](docs/TEST_PLAN.md) を参照してください。
Unit Test・Invariant Test（常識的制約の検証）・Scenario Test（60ケース）に加え、
Acceptance/Calibrationフェーズで追加した Calibration Test Dataset（100ケース超）・
Boundary Test（極端値）・Recommendation Stability Test を含め、計212件のテストを用意しています
（詳細は [docs/CALIBRATION_REPORT.md](docs/CALIBRATION_REPORT.md)）。

感度分析（主要パラメータを±10%/±20%変化させた際の推奨価格・需要・売上・利益への影響）は
`backend/scripts/sensitivity_analysis.py` で再現できます。

```bash
cd backend
python scripts/sensitivity_analysis.py
```

## External Benchmark / Historical Backtest

公開情報から収集した実在公演データに対し、現行ルールモデル(`model_version = rule_v0.1`、
27係数は固定・変更なし)がどのような推奨を出すかを測定するための基盤を
`benchmarks/` に用意しています。本番ユーザーデータ(`backend/theater_pricing.db`)とは
完全に分離されています。詳細は [benchmarks/README.md](benchmarks/README.md) を参照してください。

```bash
# リポジトリルートから実行
backend/.venv/Scripts/python.exe -m benchmarks.scripts.run_backtest

# benchmarks配下のテスト
backend/.venv/Scripts/python.exe -m pytest benchmarks/tests -q
```

- 新しい実在公演データは [benchmarks/data/public_performances.csv](benchmarks/data/public_performances.csv)
  に追記してください（列定義は `benchmarks/schema/models.py`）。テンプレートに含まれる
  `SYN-` プレフィックスの行は動作確認用の架空データ（`is_synthetic=true`）です。
- 結果は [benchmarks/results/benchmark_results.csv](benchmarks/results/benchmark_results.csv)、
  レポートは [docs/PUBLIC_BENCHMARK_REPORT.md](docs/PUBLIC_BENCHMARK_REPORT.md) に出力されます。

### rule_v0.1 と rule_v0.2

v0.1検証フェーズで発見された構造課題(Multi-performance Demand Scaling、Thin History /
Cold Start)への対応として、`rule_v0.2` を **rule_v0.1を変更せず並行して追加**しています。
設計根拠は [docs/RULE_V0_2_DESIGN.md](docs/RULE_V0_2_DESIGN.md)、実在データでの比較結果は
[docs/RULE_V0_2_EVALUATION.md](docs/RULE_V0_2_EVALUATION.md) を参照してください。

```bash
# rule_v0.1 と rule_v0.2 を同一datasetで比較し、docs/RULE_V0_2_EVALUATION.md を生成
backend/.venv/Scripts/python.exe -m benchmarks.scripts.compare_model_versions
```

**現時点の結論(2026-07時点)**: NOT ENOUGH DATA。rule_v0.2は実在2団体で一貫した
方向性の改善(demand_coverage_ratio・Venue Fitの改善)を示したが、サンプル数が
少なすぎるため一般化の確証には至っていない。ただしCold Start / Data Sufficiency
ガードレール(`backend/app/calculation/confidence.py`)は、サンプル数に依存せず
論理的に正しい安全機構であるため採用している。**現行プロダクトのデフォルトは
引き続き rule_v0.1** であり、rule_v0.2は評価・比較用のセカンドモデルという位置付け。

## 計算ロジック概要

1. 過去公演の販売実績を「完売＝真の需要ではない」という前提で補正（censored data補正）
2. 直近を重視した指数減衰加重平均で基礎集客力を算出
3. 価格・曜日・時間帯・新作再演・希少性・ゲスト・特別公演・立地・会場ブランド・SNS（上限+5%）を
   乗算補正して需要を推定
4. 価格は基準価格からの乖離率に応じて単調に需要が減少するルールベースモデル
   （過去の相関から「値上げすれば需要が増える」と学習することは絶対に行わない）
5. 会場キャパ×公演回数から売上・利益・稼働率をシミュレーションし、100円刻みで価格を全探索
6. 満席重視・売上重視・利益重視・バランスの4種類で推奨価格を算出し、Venue Fitと
   説明可能性ログ（なぜこの結果になったか）を提示

詳細な数式・根拠は [docs/CALCULATION_LOGIC.md](docs/CALCULATION_LOGIC.md) を参照してください。

## 将来のML移行方針

`DemandEstimator` インターフェースを実装した `MLDemandEstimator` に差し替えることで、
需要予測部分のみを機械学習モデルに置き換え可能です。前回動員・直近平均・簡易補正の3種類の
Baselineを上回った場合のみ採用する方針とし、Venue Fit Accuracy・Price Safety・Revenue Regret
といったサービス固有指標も含めて評価します。詳細は [docs/ML_PLAN.md](docs/ML_PLAN.md) を参照してください。

## セキュリティ

### 実装済みの対策

- 入力値バリデーション：全APIエンドポイントでPydanticによる型・範囲チェック
  （文字列長・数値範囲・価格上限下限の整合性など）
- SQLインジェクション対策：SQLAlchemy ORM経由のみでDBアクセスし、生SQL文字列結合は行わない
- XSS対策：Reactの標準エスケープを使用し、`dangerouslySetInnerHTML` は使用しない
- CORS：許可オリジンを環境変数 `CORS_ALLOW_ORIGINS` で明示指定（デフォルトはローカル開発用のみ）
- CSRF：Cookieベースの認証・セッションを持たないステートレスJSON APIのため、CSRFの実害は限定的
  （認証機能を追加する際はCSRFトークンまたはSameSite Cookie設計を再検討すること）
- secrets管理：`.env` はGit管理対象外（`.gitignore`）。コード内にシークレットは埋め込まない
- 本番でのdebug無効化：`ENVIRONMENT=production` 時、FastAPIの `debug` と `/docs` `/redoc`
  `/openapi.json` を無効化

### 公開前セキュリティチェックリスト

- [ ] `.env` に本番用のシークレット・DB接続情報を設定し、リポジトリに含まれていないことを確認する
- [ ] `CORS_ALLOW_ORIGINS` を本番フロントエンドのオリジンのみに限定する
- [ ] `ENVIRONMENT=production` を設定し、`/docs` 等が無効化されていることを確認する
- [ ] `DATABASE_URL` を本番DB（PostgreSQL等）に向け、SQLiteファイルを公開環境に置かない
- [ ] 依存パッケージの脆弱性スキャン（`pip list --outdated` / `npm audit`）を実行し、
      重大な脆弱性がないか確認する（本プロジェクトの `npm audit` 指摘は現時点でdevDependency
      （eslint/vite開発サーバー）に限定されており、本番ビルド成果物には含まれない）
- [ ] レートリミット（例: `slowapi` 等）を追加し、`/api/simulate` への過剰リクエストを防ぐ
      （MVPでは未実装。将来追加可能な構成にしている）
- [ ] HTTPS終端・リバースプロキシ（nginx等）を経由させ、平文HTTPで公開しない
- [ ] ログに個人情報・シークレットが出力されていないか確認する

## 免責事項

本ツールが提示する価格・稼働率・売上・利益・推奨シナリオは、入力された過去実績と条件に基づく
**参考値**です。結果画面には以下の注意書きを表示しています。

> 本シミュレーションは過去実績と入力条件に基づく参考値です。実際の販売結果を保証するものではありません。

このツールは経営・興行判断そのものを保証するものではなく、主催者が価格・客席数・会場・公演数の
トレードオフを合理的に検討するための補助ツールです。

## Phase 2 TODO

**目的**: Real-world benchmark dataset expansion

優先順位:

1. 劇団チョコレートケーキのusable historyとなる実在データの追加
2. ザ・ギースのusable historyとなる実在データの追加
3. かが屋の追加usable history(現在1件のみ)
4. 9〜15公演bucketの充足(現在evaluatedデータ0件)

**v0.2再評価条件**: 最低3団体以上 かつ 各団体2件以上のusable historical targetsが揃うまで、
Accessibility Gain等のrule_v0.2係数の再チューニングは行わない。
