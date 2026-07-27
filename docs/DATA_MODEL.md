# DATA_MODEL.md

MVPとして扱いやすいよう、正規化しすぎずSQLite（将来PostgreSQL移行可能なSQLAlchemy ORM）で実装する。

## groups（団体）
| column | type | note |
|---|---|---|
| id | PK | |
| name | str | 団体名 |
| genre | enum | play / conte / other |
| years_active | int | 活動年数 |
| sns_x_followers | int | |
| sns_instagram_followers | int | |
| sns_youtube_subscribers | int | |
| sns_other_followers | int | |
| created_at | datetime | |

## productions（公演企画。過去公演・今回公演の両方をこのテーブルで表す）
| column | type | note |
|---|---|---|
| id | PK | |
| group_id | FK groups | |
| is_past | bool | True=過去実績, False=今回のシミュレーション対象 |
| name | str | 公演名（過去のみ必須） |
| prefecture | str | 都道府県 |
| area | str | エリア（任意テキスト） |
| performance_date | date | nullable（今回はシミュレーション対象日） |
| is_new_work | bool | 新作=True / 再演=False |
| is_weekend_holiday | bool | 土日祝=True |
| is_evening | bool | 夜=True / 昼=False |
| rarity_level | enum | low / mid / high （希少性、今回公演のみ使用） |
| has_guest | bool | ゲスト有無（今回公演のみ使用） |
| is_special | bool | 特別公演か（今回公演のみ使用） |
| price_min | int | 希望価格下限（今回公演のみ） |
| price_max | int | 希望価格上限（今回公演のみ） |
| num_performances_candidates | JSON list[int] | 公演回数候補（今回公演のみ） |

過去公演固有の実績値（会場・価格・販売枚数等）は `past_performance_sales` に分離する
（同じ production が複数会場にまたがることは想定しないため1:1だが、将来のツアー公演拡張を考慮し分離）。

## past_performance_sales（過去公演の実績）
| column | type | note |
|---|---|---|
| id | PK | |
| production_id | FK productions | is_past=True の production に対応 |
| venue_name | str | |
| capacity | int | 1公演あたりキャパ |
| ticket_price | int | |
| num_performances | int | 公演回数 |
| tickets_sold | int | 総販売枚数（全公演合計） |
| sold_out | bool | |
| days_before_sold_out | int nullable | 完売した場合のみ |

`tickets_sold` は真の需要ではなく **観測された censored data**。
`sold_out=True` の場合、真の需要は `tickets_sold` 以上である可能性がある
（`CALCULATION_LOGIC.md` 7章の補正ロジック参照）。

## venues（今回公演の候補会場）
| column | type | note |
|---|---|---|
| id | PK | |
| production_id | FK productions | 今回公演に紐づく候補 |
| name | str | |
| area | str | |
| capacity | int | 1公演あたりキャパ |
| venue_cost | int | 会場費（1公演あたり想定） |
| walk_minutes | int | 駅徒歩分数 |
| location_rating | int(1-5) | 立地評価 |
| brand_rating | int(1-5) | 会場ブランド評価 |

## simulation_runs（シミュレーション実行単位）
| column | type | note |
|---|---|---|
| id | PK | |
| production_id | FK productions | |
| model_version | str | DemandEstimatorのバージョン文字列 |
| created_at | datetime | |
| base_attendance_power | float | 算出済み基礎集客力（説明可能性の起点） |
| explanation_json | JSON | 補正要因の内訳（説明可能性ログ） |

## simulation_scenarios（会場×価格×公演回数の1シナリオ）
| column | type | note |
|---|---|---|
| id | PK | |
| run_id | FK simulation_runs | |
| venue_id | FK venues | |
| price | int | |
| num_performances | int | |
| expected_demand | float | |
| available_seats | int | |
| expected_sold | float | |
| occupancy_rate | float | |
| revenue | float | |
| profit | float | |
| venue_fit | enum | too_small / good / slightly_large / too_large |
| is_recommended_balance | bool | |
| is_recommended_sellout | bool | |
| is_recommended_revenue | bool | |
| is_recommended_profit | bool | |

## actual_results（公演終了後の実績登録。predictionとの紐付けでML教師データ化）
| column | type | note |
|---|---|---|
| id | PK | |
| run_id | FK simulation_runs | どの予測に対する実績か |
| scenario_id | FK simulation_scenarios nullable | 採用したシナリオがあれば紐付け |
| actual_price | int | |
| actual_venue_name | str | |
| actual_num_performances | int | |
| actual_tickets_sold | int | |
| actual_occupancy_rate | float | |
| actual_sold_out | bool | |
| actual_days_before_sold_out | int nullable | |
| actual_revenue | float | |
| recorded_at | datetime | |

## ER概要
```
groups 1--n productions 1--n past_performance_sales
productions 1--n venues
productions 1--n simulation_runs 1--n simulation_scenarios
simulation_runs 1--n actual_results
```
