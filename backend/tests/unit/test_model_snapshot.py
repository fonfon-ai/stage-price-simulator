"""rule_v0.1 の係数が凍結されていることを保証する回帰テスト。

External Benchmarkの実施中に誤って係数を変更してしまうことを防ぐためのガード。
値を変える場合はモデルバージョンも変更すること。
"""
from app.calculation.model_snapshot import model_version, snapshot

EXPECTED_MODEL_VERSION = "rule_v0.1"

EXPECTED_SNAPSHOT = {
    "ATTENDANCE_DECAY": 0.6,
    "SOLD_OUT_BASE_CORRECTION": 1.05,
    "SOLD_OUT_EARLY_BONUS_PER_DAY": 0.01,
    "SOLD_OUT_CORRECTION_CAP": 1.20,
    "PRICE_ELASTICITY": 0.9,
    "PRICE_FACTOR_MIN": 0.4,
    "PRICE_FACTOR_MAX": 1.3,
    "WEEKEND_HOLIDAY_FACTOR": 1.08,
    "EVENING_FACTOR": 1.05,
    "NEW_WORK_FACTOR": 1.05,
    "RARITY_FACTOR": {"low": 1.00, "mid": 1.05, "high": 1.12},
    "GUEST_FACTOR": 1.07,
    "SPECIAL_FACTOR": 1.10,
    "LOCATION_BASE": 0.90,
    "LOCATION_RATING_STEP": 0.02,
    "LOCATION_WALK_PENALTY_PER_MIN": 0.004,
    "LOCATION_FACTOR_MIN": 0.85,
    "LOCATION_FACTOR_MAX": 1.15,
    "BRAND_BASE": 0.95,
    "BRAND_RATING_STEP": 0.02,
    "BRAND_FACTOR_MIN": 0.90,
    "BRAND_FACTOR_MAX": 1.15,
    "SNS_WEIGHT_X": 1.0,
    "SNS_WEIGHT_INSTAGRAM": 1.0,
    "SNS_WEIGHT_YOUTUBE": 1.2,
    "SNS_WEIGHT_OTHER": 0.5,
    "SNS_FACTOR_SCALE": 0.006,
    "SNS_FACTOR_CAP": 0.05,
    "POOL_EXPONENT": 0.85,
    "PRICE_STEP": 100,
    "VENUE_FIT_TOO_SMALL_THRESHOLD": 1.00,
    "VENUE_FIT_GOOD_MIN": 0.75,
    "VENUE_FIT_SLIGHTLY_LARGE_MIN": 0.55,
    "SELLOUT_TARGET_OCCUPANCY": 0.90,
    "BALANCE_WEIGHT_OCCUPANCY": 0.30,
    "BALANCE_WEIGHT_REVENUE": 0.30,
    "BALANCE_WEIGHT_PROFIT": 0.30,
    "BALANCE_WEIGHT_DISCOUNT_PENALTY": 0.10,
    "BALANCE_TARGET_OCCUPANCY_RANGE": (0.85, 0.97),
    "RECOMMENDED_RANGE_SCORE_THRESHOLD": 0.95,
    "MODEL_VERSION": "rule_v0.1",
}


def test_model_version_is_frozen_at_rule_v0_1():
    assert model_version() == EXPECTED_MODEL_VERSION


def test_all_27_plus_coefficients_are_unchanged():
    current = snapshot()
    assert current == EXPECTED_SNAPSHOT, (
        "rule_v0.1 の係数が変更されています。External Benchmarkフェーズ中は係数固定が方針です。"
    )
