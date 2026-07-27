"""テスト用のデータ生成ヘルパー。"""
from __future__ import annotations

import datetime as dt

from app.calculation.types import (
    CurrentProductionInput,
    DemandFeatures,
    Genre,
    GroupInfo,
    PastPerformance,
    RarityLevel,
    VenueCandidate,
)


def make_group(**overrides) -> GroupInfo:
    defaults = dict(
        name="テスト劇団",
        genre=Genre.PLAY,
        years_active=5,
        sns_x_followers=1000,
        sns_instagram_followers=500,
        sns_youtube_subscribers=200,
        sns_other_followers=0,
    )
    defaults.update(overrides)
    return GroupInfo(**defaults)


def make_past_performance(days_ago: int = 30, **overrides) -> PastPerformance:
    defaults = dict(
        name="過去公演",
        performance_date=dt.date(2026, 1, 1) - dt.timedelta(days=days_ago),
        capacity=200,
        price=3500,
        num_performances=1,
        tickets_sold=150,
        sold_out=False,
        is_new_work=True,
        is_weekend_holiday=False,
        is_evening=False,
        days_before_sold_out=None,
    )
    defaults.update(overrides)
    return PastPerformance(**defaults)


def make_past_performances(n: int = 3, **common) -> list[PastPerformance]:
    return [
        make_past_performance(days_ago=(i + 1) * 90, **common) for i in range(n)
    ]


def make_current_production(**overrides) -> CurrentProductionInput:
    defaults = dict(
        area="東京都",
        is_new_work=True,
        is_weekend_holiday=True,
        is_evening=False,
        rarity_level=RarityLevel.MID,
        has_guest=False,
        is_special=False,
        price_min=3000,
        price_max=4500,
    )
    defaults.update(overrides)
    return CurrentProductionInput(**defaults)


def make_venue(**overrides) -> VenueCandidate:
    defaults = dict(
        name="テスト会場",
        area="東京都",
        capacity=200,
        venue_cost=200000,
        walk_minutes=5,
        location_rating=3,
        brand_rating=3,
    )
    defaults.update(overrides)
    return VenueCandidate(**defaults)


def make_features(**overrides) -> DemandFeatures:
    defaults = dict(
        group=make_group(),
        past_performances=make_past_performances(),
        current_production=make_current_production(),
        venue=make_venue(),
        price=3800,
        num_performances=1,
    )
    defaults.update(overrides)
    return DemandFeatures(**defaults)
