/**
 * 補正係数の定数。rule_v0.1。
 * backend/app/calculation/constants.py の値をそのまま転記したもの。
 * 値を変更する場合は両方のファイルを同期させること
 * (backend/tests/unit/test_model_snapshot.py がPython側の値を固定している)。
 */

// 基礎集客力: 直近を重視する指数減衰の係数（直近=1, 1つ前=DECAY, 2つ前=DECAY^2 ...）
export const ATTENDANCE_DECAY = 0.6;

// 完売公演の censored data 補正
export const SOLD_OUT_BASE_CORRECTION = 1.05;
export const SOLD_OUT_EARLY_BONUS_PER_DAY = 0.01;
export const SOLD_OUT_CORRECTION_CAP = 1.2;

// 価格弾力性（ルールベース、過去データからは学習しない）
export const PRICE_ELASTICITY = 0.9;
export const PRICE_FACTOR_MIN = 0.4;
export const PRICE_FACTOR_MAX = 1.3;

// 曜日・時間帯・企画属性補正
export const WEEKEND_HOLIDAY_FACTOR = 1.08;
export const EVENING_FACTOR = 1.05;
export const NEW_WORK_FACTOR = 1.05;
export const RARITY_FACTOR: Record<"low" | "mid" | "high", number> = {
  low: 1.0,
  mid: 1.05,
  high: 1.12,
};
export const GUEST_FACTOR = 1.07;
export const SPECIAL_FACTOR = 1.1;

// 立地・会場ブランド補正
export const LOCATION_BASE = 0.9;
export const LOCATION_RATING_STEP = 0.02;
export const LOCATION_WALK_PENALTY_PER_MIN = 0.004;
export const LOCATION_FACTOR_MIN = 0.85;
export const LOCATION_FACTOR_MAX = 1.15;

export const BRAND_BASE = 0.95;
export const BRAND_RATING_STEP = 0.02;
export const BRAND_FACTOR_MIN = 0.9;
export const BRAND_FACTOR_MAX = 1.15;

// SNS補正（補助情報。過大評価を防ぐため上限をキャップ）
export const SNS_WEIGHT_X = 1.0;
export const SNS_WEIGHT_INSTAGRAM = 1.0;
export const SNS_WEIGHT_YOUTUBE = 1.2;
export const SNS_WEIGHT_OTHER = 0.5;
export const SNS_FACTOR_SCALE = 0.006;
export const SNS_FACTOR_CAP = 0.05;

// 公演回数の逓減モデル（観客プールの重複を考慮）
export const POOL_EXPONENT = 0.85;

// 価格探索の刻み幅
export const PRICE_STEP = 100;

// Venue Fit 判定の稼働率しきい値
export const VENUE_FIT_TOO_SMALL_THRESHOLD = 1.0;
export const VENUE_FIT_GOOD_MIN = 0.75;
export const VENUE_FIT_SLIGHTLY_LARGE_MIN = 0.55;

// 満席重視の目標稼働率下限
export const SELLOUT_TARGET_OCCUPANCY = 0.9;

// バランススコアの重み
export const BALANCE_WEIGHT_OCCUPANCY = 0.3;
export const BALANCE_WEIGHT_REVENUE = 0.3;
export const BALANCE_WEIGHT_PROFIT = 0.3;
export const BALANCE_WEIGHT_DISCOUNT_PENALTY = 0.1;
export const BALANCE_TARGET_OCCUPANCY_RANGE: [number, number] = [0.85, 0.97];

// 推奨価格帯: バランススコアの何%以内を「帯」に含めるか
export const RECOMMENDED_RANGE_SCORE_THRESHOLD = 0.95;

export const MODEL_VERSION = "rule_v0.1";
