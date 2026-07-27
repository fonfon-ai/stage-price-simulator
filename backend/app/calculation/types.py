"""計算エンジンで使うデータ構造。FastAPI/DBに依存しない純粋なdataclass群。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Genre(str, Enum):
    PLAY = "play"
    CONTE = "conte"
    OTHER = "other"


class RarityLevel(str, Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"


class VenueFitCategory(str, Enum):
    TOO_SMALL = "too_small"
    GOOD = "good"
    SLIGHTLY_LARGE = "slightly_large"
    TOO_LARGE = "too_large"


@dataclass
class GroupInfo:
    name: str
    genre: Genre
    years_active: int
    sns_x_followers: int = 0
    sns_instagram_followers: int = 0
    sns_youtube_subscribers: int = 0
    sns_other_followers: int = 0


@dataclass
class PastPerformance:
    name: str
    performance_date: date
    capacity: int
    price: int
    num_performances: int
    tickets_sold: int
    sold_out: bool
    is_new_work: bool
    is_weekend_holiday: bool
    is_evening: bool
    days_before_sold_out: int | None = None
    prefecture: str = ""
    area: str = ""
    venue_name: str = ""


@dataclass
class CurrentProductionInput:
    area: str
    is_new_work: bool
    is_weekend_holiday: bool
    is_evening: bool
    rarity_level: RarityLevel
    has_guest: bool
    is_special: bool
    price_min: int
    price_max: int
    performance_date: date | None = None


@dataclass
class VenueCandidate:
    name: str
    area: str
    capacity: int
    venue_cost: int
    walk_minutes: int
    location_rating: int  # 1-5
    brand_rating: int  # 1-5


@dataclass
class ExplanationItem:
    factor: str
    multiplier: float
    description: str


@dataclass
class DemandFeatures:
    group: GroupInfo
    past_performances: list[PastPerformance]
    current_production: CurrentProductionInput
    venue: VenueCandidate
    price: int
    num_performances: int


@dataclass
class DemandEstimate:
    base_attendance_power: float
    baseline_price: float
    expected_demand_per_performance: float
    total_expected_demand: float
    explanation: list[ExplanationItem] = field(default_factory=list)


@dataclass
class ScenarioResult:
    venue_name: str
    price: int
    num_performances: int
    available_seats: int
    expected_demand: float
    expected_sold: float
    occupancy_rate: float
    revenue: float
    profit: float
    venue_fit: VenueFitCategory
    venue_fit_message: str
