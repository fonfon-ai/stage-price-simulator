"""Calibration Test Dataset。

「予測精度」ではなく「意思決定として常識的か」を検証するための、100件以上の
代表的シナリオ集合。各ケースにタグを付与し、docs/CALIBRATION_REPORT.md 記載の
チェック観点(小規模団体に巨大会場を勧めない、SNSだけで大会場を勧めない等)を
自動テストできるようにする。
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from app.calculation.types import (
    CurrentProductionInput,
    Genre,
    GroupInfo,
    PastPerformance,
    RarityLevel,
    VenueCandidate,
)


@dataclass
class CalibrationCase:
    label: str
    tags: list[str]
    group: GroupInfo
    past_performances: list[PastPerformance]
    current_production: CurrentProductionInput
    venues: list[VenueCandidate]
    num_performances_candidates: list[int] = field(default_factory=lambda: [1])


def _perf(days_ago, tickets_sold, capacity=None, price=3500, num_performances=1,
          sold_out=False, days_before_sold_out=None, is_new_work=True,
          is_weekend_holiday=False, is_evening=False):
    return PastPerformance(
        name=f"公演-{days_ago}",
        performance_date=dt.date(2026, 1, 1) - dt.timedelta(days=days_ago),
        capacity=capacity if capacity is not None else max(tickets_sold, 10),
        price=price,
        num_performances=num_performances,
        tickets_sold=tickets_sold,
        sold_out=sold_out,
        days_before_sold_out=days_before_sold_out,
        is_new_work=is_new_work,
        is_weekend_holiday=is_weekend_holiday,
        is_evening=is_evening,
    )


def _group(sns_level="low", genre=Genre.PLAY, years_active=5):
    sns_values = {
        "none": (0, 0, 0, 0),
        "low": (500, 300, 100, 0),
        "mid": (5000, 3000, 1000, 200),
        "high": (50000, 30000, 10000, 2000),
        "huge": (500000, 300000, 100000, 20000),
    }
    x, ig, yt, other = sns_values[sns_level]
    return GroupInfo(
        name=f"団体-{sns_level}",
        genre=genre,
        years_active=years_active,
        sns_x_followers=x,
        sns_instagram_followers=ig,
        sns_youtube_subscribers=yt,
        sns_other_followers=other,
    )


def _current(price_min, price_max, is_weekend_holiday=True, is_new_work=True,
             rarity=RarityLevel.MID, has_guest=False, is_special=False, is_evening=False):
    return CurrentProductionInput(
        area="東京都",
        is_new_work=is_new_work,
        is_weekend_holiday=is_weekend_holiday,
        is_evening=is_evening,
        rarity_level=rarity,
        has_guest=has_guest,
        is_special=is_special,
        price_min=price_min,
        price_max=price_max,
    )


def _venue(
    capacity, venue_cost=None, name="会場", location_rating=3, brand_rating=3, walk_minutes=5
):
    return VenueCandidate(
        name=name,
        area="東京都",
        capacity=capacity,
        venue_cost=venue_cost if venue_cost is not None else capacity * 1000,
        walk_minutes=walk_minutes,
        location_rating=location_rating,
        brand_rating=brand_rating,
    )


def generate_calibration_cases() -> list[CalibrationCase]:
    cases: list[CalibrationCase] = []

    # --- 1. 動員規模別(30-50 / 100 / 200 / 300-500) x 過去公演件数(1件 / 5件以上) ---
    attendance_levels = {
        "attendance_30_50": 40,
        "attendance_100": 100,
        "attendance_200": 200,
        "attendance_300_500": 400,
    }
    for level_tag, base in attendance_levels.items():
        # 過去公演1件のみ
        cases.append(
            CalibrationCase(
                label=f"{level_tag}_single_past",
                tags=[level_tag, "past_performances_1", "weekday_or_weekend_mixed"],
                group=_group("low"),
                past_performances=[_perf(days_ago=60, tickets_sold=base, capacity=int(base * 1.1))],
                current_production=_current(2500, 4000),
                venues=[_venue(int(base * 1.1))],
                num_performances_candidates=[1],
            )
        )
        # 過去公演5件以上(安定推移)
        cases.append(
            CalibrationCase(
                label=f"{level_tag}_5plus_past",
                tags=[level_tag, "past_performances_5plus"],
                group=_group("mid"),
                past_performances=[
                    _perf(
                        days_ago=(i + 1) * 60,
                        tickets_sold=base + (i % 2) * 5,
                        capacity=int(base * 1.2),
                    )
                    for i in range(6)
                ],
                current_production=_current(2500, 4500),
                venues=[_venue(int(base * 1.2))],
                num_performances_candidates=[1, 2],
            )
        )

    # --- 2. 急成長 / 動員が落ちている団体 ---
    cases.append(
        CalibrationCase(
            label="rapid_growth_group",
            tags=["rapid_growth", "past_performances_5plus"],
            group=_group("mid"),
            past_performances=[
                _perf(days_ago=180, tickets_sold=40),
                _perf(days_ago=150, tickets_sold=60),
                _perf(days_ago=90, tickets_sold=100),
                _perf(days_ago=45, tickets_sold=160),
                _perf(days_ago=15, tickets_sold=220, capacity=250),
            ],
            current_production=_current(3000, 4500),
            venues=[_venue(250), _venue(500, name="会場(大)")],
            num_performances_candidates=[1, 2],
        )
    )
    cases.append(
        CalibrationCase(
            label="declining_group",
            tags=["declining_attendance", "past_performances_5plus"],
            group=_group("mid"),
            past_performances=[
                _perf(days_ago=180, tickets_sold=220),
                _perf(days_ago=150, tickets_sold=190),
                _perf(days_ago=90, tickets_sold=150),
                _perf(days_ago=45, tickets_sold=110),
                _perf(days_ago=15, tickets_sold=90),
            ],
            current_production=_current(3000, 4500),
            venues=[_venue(250)],
            num_performances_candidates=[1],
        )
    )

    # --- 3. 完売パターン ---
    cases.append(
        CalibrationCase(
            label="sold_out_normal",
            tags=["sold_out", "attendance_200"],
            group=_group("mid"),
            past_performances=[
                _perf(
                    days_ago=60,
                    tickets_sold=200,
                    capacity=200,
                    sold_out=True,
                    days_before_sold_out=2,
                )
                for _ in range(1)
            ],
            current_production=_current(3000, 4500),
            venues=[_venue(220)],
        )
    )
    cases.append(
        CalibrationCase(
            label="sold_out_very_early",
            tags=["sold_out_early", "attendance_200"],
            group=_group("high"),
            past_performances=[
                _perf(
                    days_ago=60,
                    tickets_sold=200,
                    capacity=200,
                    sold_out=True,
                    days_before_sold_out=30,
                )
            ],
            current_production=_current(3500, 5500),
            venues=[_venue(220), _venue(400, name="会場(大)")],
        )
    )
    cases.append(
        CalibrationCase(
            label="never_sold_out_long_sale",
            tags=["not_sold_out", "attendance_100"],
            group=_group("low"),
            past_performances=[
                _perf(days_ago=60, tickets_sold=90, capacity=200, sold_out=False)
            ],
            current_production=_current(2000, 3500),
            venues=[_venue(200)],
        )
    )

    # --- 4. SNSだけ非常に大きい団体 / SNSが小さいが実動員が強い団体 ---
    cases.append(
        CalibrationCase(
            label="sns_huge_low_attendance",
            tags=["sns_huge_only", "attendance_30_50"],
            group=_group("huge"),
            past_performances=[_perf(days_ago=60, tickets_sold=40, capacity=60)],
            current_production=_current(2500, 4000),
            venues=[_venue(60), _venue(500, name="会場(大)")],
        )
    )
    cases.append(
        CalibrationCase(
            label="sns_small_strong_attendance",
            tags=["sns_low_strong_attendance", "attendance_300_500"],
            group=_group("none"),
            past_performances=[_perf(days_ago=60, tickets_sold=420, capacity=450)],
            current_production=_current(3500, 5000),
            venues=[_venue(450)],
        )
    )

    # --- 5. 平日 / 土日祝、新作 / 再演、希少公演、頻繁公演 ---
    cases.append(
        CalibrationCase(
            label="weekday_show",
            tags=["weekday"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=120, is_weekend_holiday=False)],
            current_production=_current(3000, 4000, is_weekend_holiday=False),
            venues=[_venue(150)],
        )
    )
    cases.append(
        CalibrationCase(
            label="weekend_holiday_show",
            tags=["weekend_holiday"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=120, is_weekend_holiday=True)],
            current_production=_current(3000, 4000, is_weekend_holiday=True),
            venues=[_venue(150)],
        )
    )
    cases.append(
        CalibrationCase(
            label="new_work_show",
            tags=["new_work"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=120, is_new_work=False)],
            current_production=_current(3000, 4000, is_new_work=True),
            venues=[_venue(150)],
        )
    )
    cases.append(
        CalibrationCase(
            label="revival_show",
            tags=["revival"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=120, is_new_work=False)],
            current_production=_current(3000, 4000, is_new_work=False),
            venues=[_venue(150)],
        )
    )
    cases.append(
        CalibrationCase(
            label="rare_show",
            tags=["rarity_high"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=120)],
            current_production=_current(3000, 5000, rarity=RarityLevel.HIGH),
            venues=[_venue(150)],
        )
    )
    cases.append(
        CalibrationCase(
            label="frequent_performer",
            tags=["frequent_performances", "past_performances_5plus"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=(i + 1) * 20, tickets_sold=150) for i in range(8)],
            current_production=_current(3000, 4500),
            venues=[_venue(180)],
            num_performances_candidates=[3, 5, 8],
        )
    )

    # --- 6. 会場サイズ(小会場 / 適正 / 明らかに大きすぎる)、会場費(高い/安い) ---
    cases.append(
        CalibrationCase(
            label="small_venue_fit",
            tags=["venue_small"],
            group=_group("low"),
            past_performances=[_perf(days_ago=60, tickets_sold=80)],
            current_production=_current(2500, 3500),
            venues=[_venue(50)],
        )
    )
    cases.append(
        CalibrationCase(
            label="appropriate_venue_fit",
            tags=["venue_appropriate"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=180, capacity=200)],
            current_production=_current(3000, 4000),
            venues=[_venue(200)],
        )
    )
    cases.append(
        CalibrationCase(
            label="obviously_too_large_venue",
            tags=["venue_too_large", "attendance_30_50"],
            group=_group("low"),
            past_performances=[_perf(days_ago=60, tickets_sold=40, capacity=60)],
            current_production=_current(2500, 4000),
            venues=[_venue(2000, name="巨大会場")],
        )
    )
    cases.append(
        CalibrationCase(
            label="high_venue_cost",
            tags=["venue_cost_high"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=150)],
            current_production=_current(3000, 4500),
            venues=[_venue(180, venue_cost=2000000, name="高額会場")],
        )
    )
    cases.append(
        CalibrationCase(
            label="low_venue_cost",
            tags=["venue_cost_low"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=150)],
            current_production=_current(3000, 4500),
            venues=[_venue(180, venue_cost=10000, name="低額会場")],
        )
    )

    # --- 7. 価格帯(低/通常/高)、公演回数(1回/複数回) ---
    price_levels = {
        "price_low": (800, 1800),
        "price_normal": (3000, 4500),
        "price_high": (6000, 9000),
    }
    for tag, (pmin, pmax) in price_levels.items():
        cases.append(
            CalibrationCase(
                label=f"{tag}_single_perf",
                tags=[tag, "single_performance"],
                group=_group("mid"),
                past_performances=[_perf(days_ago=60, tickets_sold=150, price=(pmin + pmax) // 2)],
                current_production=_current(pmin, pmax),
                venues=[_venue(180)],
                num_performances_candidates=[1],
            )
        )
        cases.append(
            CalibrationCase(
                label=f"{tag}_multi_perf",
                tags=[tag, "multiple_performances"],
                group=_group("mid"),
                past_performances=[_perf(days_ago=60, tickets_sold=150, price=(pmin + pmax) // 2)],
                current_production=_current(pmin, pmax),
                venues=[_venue(180)],
                num_performances_candidates=[1, 2, 4],
            )
        )

    # --- 8. ジャンル横断(コント) x 団体規模のバリエーションを追加してケース数を拡張 ---
    genre_group_variants = [
        ("conte_unknown", Genre.CONTE, "low", 35, 1),
        ("conte_rising", Genre.CONTE, "mid", 90, 3),
        ("conte_popular", Genre.CONTE, "high", 380, 5),
        ("play_unknown", Genre.PLAY, "low", 45, 1),
        ("play_rising", Genre.PLAY, "mid", 110, 3),
        ("play_popular", Genre.PLAY, "high", 420, 5),
    ]
    for tag, genre, sns_level, base, n_past in genre_group_variants:
        for capacity_tag, capacity in [("cap_small", 60), ("cap_mid", 200), ("cap_large", 500)]:
            for weekend in (True, False):
                cases.append(
                    CalibrationCase(
                        label=f"{tag}_{capacity_tag}_{'weekend' if weekend else 'weekday'}",
                        tags=[
                            tag,
                            capacity_tag,
                            "weekend_holiday" if weekend else "weekday",
                            "past_performances_5plus" if n_past >= 5 else "past_performances_1",
                        ],
                        group=_group(sns_level, genre=genre),
                        past_performances=[
                            _perf(days_ago=(i + 1) * 45, tickets_sold=base)
                            for i in range(n_past)
                        ],
                        current_production=_current(2500, 4500, is_weekend_holiday=weekend),
                        venues=[_venue(capacity)],
                        num_performances_candidates=[1, 2],
                    )
                )

    # --- 8b. 動員規模 x 会場規模 x 平日/土日祝のクロス ---
    venue_categories = {
        "venue_small": 60,
        "venue_appropriate": 200,
        "venue_too_large": 1500,
    }
    for level_tag, base in attendance_levels.items():
        for venue_tag, capacity in venue_categories.items():
            for weekend in (True, False):
                cases.append(
                    CalibrationCase(
                        label=f"{level_tag}_{venue_tag}_{'weekend' if weekend else 'weekday'}",
                        tags=[
                            level_tag,
                            venue_tag,
                            "weekend_holiday" if weekend else "weekday",
                        ],
                        group=_group("low" if base < 100 else "mid"),
                        past_performances=[_perf(days_ago=60, tickets_sold=base)],
                        current_production=_current(2500, 4500, is_weekend_holiday=weekend),
                        venues=[_venue(capacity)],
                        num_performances_candidates=[1],
                    )
                )

    # --- 8c. 価格帯 x 平日/土日祝のクロス ---
    for tag, (pmin, pmax) in price_levels.items():
        for weekend in (True, False):
            cases.append(
                CalibrationCase(
                    label=f"{tag}_{'weekend' if weekend else 'weekday'}_cross",
                    tags=[tag, "weekend_holiday" if weekend else "weekday"],
                    group=_group("mid"),
                    past_performances=[
                        _perf(days_ago=60, tickets_sold=150, price=(pmin + pmax) // 2)
                    ],
                    current_production=_current(pmin, pmax, is_weekend_holiday=weekend),
                    venues=[_venue(180)],
                    num_performances_candidates=[1],
                )
            )

    # --- 9. ゲスト有無 / 特別公演 ---
    cases.append(
        CalibrationCase(
            label="guest_show",
            tags=["guest_present"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=150)],
            current_production=_current(3000, 4500, has_guest=True),
            venues=[_venue(180)],
        )
    )
    cases.append(
        CalibrationCase(
            label="special_show",
            tags=["special_event"],
            group=_group("mid"),
            past_performances=[_perf(days_ago=60, tickets_sold=150)],
            current_production=_current(3000, 5000, is_special=True),
            venues=[_venue(180)],
        )
    )

    return cases
