# ARCHITECTURE.md

## 技術構成（過剰複雑化を避ける）

- Backend: Python / FastAPI / SQLAlchemy（開発時SQLite、本番PostgreSQL移行可能なORM設計）/ Pydantic v2
- Frontend: React + TypeScript + Vite（Next.jsではなくViteを採用。理由は下記）
- Calculation: Python（backend内の独立パッケージとして分離、FastAPIに依存しない）
- Testing: pytest（backend）、Vitest + Testing Library（frontend）

### Next.js ではなく Vite+React を採用した理由

要件19「技術構成」ではNext.jsが推奨として挙げられているが、要件18に「過剰に複雑化しないでください」
とあるため、本アプリがSSR/SEOを必要としないフォーム主体のSPA（ステップウィザード＋結果ダッシュボード）
であることを踏まえ、ビルド・デプロイがシンプルなVite+React SPAを採用した。API通信のみでNext.jsの
サーバーサイド機能（ISR/SSR/APIルート等）を使う必然性がないための判断。将来SEOが必要なランディング
ページが必要になった場合はNext.js移行も可能（コンポーネント単位で流用しやすいReact構成にしている）。

## レイヤー構成

```
frontend/            React SPA（ステップ入力フォーム + 結果ダッシュボード）
backend/
  app/
    main.py          FastAPI アプリ、CORS/セキュリティミドルウェア
    api/              ルーター（groups, productions, venues, simulate, actual_results）
    schemas/          Pydantic モデル（入力バリデーション）
    models/           SQLAlchemy モデル（DATA_MODEL.md準拠）
    db.py             DBセッション（開発:SQLite、環境変数でPostgreSQLへ切替可能）
    calculation/
      demand_estimator.py   DemandEstimator (ABC) / RuleBasedDemandEstimator
      constants.py          全補正係数（CALCULATION_LOGIC.md準拠）
      simulator.py          PerformanceSimulator（キャパ制約・売上・利益）
      recommender.py        Recommender（満席/売上/利益/バランス価格、価格探索）
      venue_fit.py          VenueFit判定（テンプレート文生成）
      explain.py            説明可能性ログの組み立て
      types.py              dataclass群（DemandFeatures, DemandEstimate, ScenarioResult等）
  tests/
    unit/             売上/利益/キャパ/価格探索/補正値/基礎需要/VenueFit
    invariant/        SPEC.md 15章の不変条件
    scenario/         50ケース以上のシナリオテスト
```

## DemandEstimator の差し替え可能設計

```python
class DemandEstimator(ABC):
    @abstractmethod
    def estimate_demand(self, features: DemandFeatures) -> DemandEstimate:
        ...

class RuleBasedDemandEstimator(DemandEstimator):
    # MVP実装。CALCULATION_LOGIC.md の全ロジックをここに実装する。
    ...

# 将来:
# class MLDemandEstimator(DemandEstimator):
#     def __init__(self, model_path: str): self.model = joblib.load(model_path)
#     def estimate_demand(self, features): ...  # scikit-learn互換モデルで推論
```

`PerformanceSimulator` と `Recommender` は `DemandEstimator` の具象実装に依存せず、
`DemandEstimate`（dataclass）のみに依存する。したがって `RuleBasedDemandEstimator` を
`MLDemandEstimator` に差し替えても、シミュレーション/推奨ロジックは変更不要。
現時点ではMLパッケージ（scikit-learn等）への依存は導入しない
（`ML_PLAN.md` にインターフェース設計のみ記載）。

## API概要

- `POST /api/groups` `POST /api/productions` `POST /api/venues` — 入力データ登録
- `POST /api/simulate` — production_id を受け取り、全候補会場×全価格×全公演回数を計算し
  `simulation_runs` / `simulation_scenarios` を保存、結果を返す
- `POST /api/actual_results` — 公演終了後の実績登録（run_idと紐付け）
- 全エンドポイントは Pydantic による入力バリデーションを行い、SQLAlchemyのORM経由でのみDBアクセス
  （生SQL文字列結合を行わずSQLインジェクションを防止）

## セキュリティ設計

`README.md` の「セキュリティ」節を参照。CORS許可オリジンは環境変数で明示指定、
DEBUGは本番で無効、シークレットは`.env`管理し`.gitignore`対象とする。
