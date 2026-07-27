"""API入出力スキーマ（Pydantic）。入力バリデーションによりSQLインジェクション/不正値を防止する。"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator


class GroupInfoIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    genre: str = Field(pattern="^(play|conte|other)$")
    years_active: int = Field(ge=0, le=100)
    sns_x_followers: int = Field(default=0, ge=0)
    sns_instagram_followers: int = Field(default=0, ge=0)
    sns_youtube_subscribers: int = Field(default=0, ge=0)
    sns_other_followers: int = Field(default=0, ge=0)


class PastPerformanceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    performance_date: dt.date
    prefecture: str = Field(default="", max_length=50)
    area: str = Field(default="", max_length=100)
    venue_name: str = Field(default="", max_length=200)
    capacity: int = Field(gt=0, le=100000)
    price: int = Field(gt=0, le=1000000)
    num_performances: int = Field(gt=0, le=100)
    tickets_sold: int = Field(ge=0, le=10000000)
    sold_out: bool = False
    days_before_sold_out: int | None = Field(default=None, ge=0, le=365)
    is_new_work: bool = True
    is_weekend_holiday: bool = False
    is_evening: bool = False

    @field_validator("tickets_sold")
    @classmethod
    def sold_not_exceed_seats(cls, v: int, info) -> int:
        capacity = info.data.get("capacity")
        num_performances = info.data.get("num_performances")
        if capacity and num_performances and v > capacity * num_performances:
            raise ValueError("tickets_sold must not exceed capacity * num_performances")
        return v


class CurrentProductionIn(BaseModel):
    area: str = Field(default="", max_length=100)
    performance_date: dt.date | None = None
    is_new_work: bool = True
    is_weekend_holiday: bool = False
    is_evening: bool = False
    rarity_level: str = Field(pattern="^(low|mid|high)$")
    has_guest: bool = False
    is_special: bool = False
    price_min: int = Field(gt=0, le=1000000)
    price_max: int = Field(gt=0, le=1000000)

    @field_validator("price_max")
    @classmethod
    def max_gte_min(cls, v: int, info) -> int:
        price_min = info.data.get("price_min")
        if price_min and v < price_min:
            raise ValueError("price_max must be >= price_min")
        return v


class VenueCandidateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    area: str = Field(default="", max_length=100)
    capacity: int = Field(gt=0, le=100000)
    venue_cost: int = Field(ge=0, le=100000000)
    walk_minutes: int = Field(ge=0, le=180)
    location_rating: int = Field(ge=1, le=5)
    brand_rating: int = Field(ge=1, le=5)


class SimulateRequest(BaseModel):
    group: GroupInfoIn
    past_performances: list[PastPerformanceIn] = Field(min_length=1, max_length=20)
    current_production: CurrentProductionIn
    venues: list[VenueCandidateIn] = Field(min_length=1, max_length=10)
    num_performances_candidates: list[int] = Field(min_length=1, max_length=10)

    @field_validator("num_performances_candidates")
    @classmethod
    def candidates_positive(cls, v: list[int]) -> list[int]:
        if any(n <= 0 or n > 100 for n in v):
            raise ValueError("num_performances_candidates must be within 1..100")
        return v


class ExplanationItemOut(BaseModel):
    factor: str
    multiplier: float
    description: str


class ScenarioOut(BaseModel):
    venue_name: str
    price: int
    num_performances: int
    available_seats: int
    expected_demand: float
    expected_sold: float
    occupancy_rate: float
    revenue: float
    profit: float
    venue_fit: str
    venue_fit_message: str


class SimulateResponse(BaseModel):
    run_id: int
    model_version: str
    base_attendance_power: float
    baseline_price: float
    recommended_price_range: tuple[int, int]
    balance_price: int
    sellout_price: int
    revenue_price: int
    profit_price: int
    balance_scenario: ScenarioOut
    sellout_scenario: ScenarioOut
    revenue_scenario: ScenarioOut
    profit_scenario: ScenarioOut
    scenarios: list[ScenarioOut]
    explanation: list[ExplanationItemOut]
    disclaimer: str


class ActualResultIn(BaseModel):
    run_id: int
    scenario_id: int | None = None
    actual_price: int = Field(gt=0, le=1000000)
    actual_venue_name: str = Field(min_length=1, max_length=200)
    actual_capacity: int | None = Field(default=None, gt=0, le=100000)
    actual_num_performances: int = Field(gt=0, le=100)
    actual_tickets_sold: int = Field(ge=0, le=10000000)
    actual_sold_out: bool = False
    actual_days_before_sold_out: int | None = Field(default=None, ge=0, le=365)
