"""SQLAlchemy ORM モデル。docs/DATA_MODEL.md に対応。"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str] = mapped_column(String(20))
    years_active: Mapped[int] = mapped_column(Integer, default=0)
    sns_x_followers: Mapped[int] = mapped_column(Integer, default=0)
    sns_instagram_followers: Mapped[int] = mapped_column(Integer, default=0)
    sns_youtube_subscribers: Mapped[int] = mapped_column(Integer, default=0)
    sns_other_followers: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow
    )

    productions: Mapped[list[Production]] = relationship(back_populates="group")


class Production(Base):
    __tablename__ = "productions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    is_past: Mapped[bool] = mapped_column(Boolean)
    name: Mapped[str] = mapped_column(String(200), default="")
    prefecture: Mapped[str] = mapped_column(String(50), default="")
    area: Mapped[str] = mapped_column(String(100), default="")
    performance_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    is_new_work: Mapped[bool] = mapped_column(Boolean, default=True)
    is_weekend_holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    is_evening: Mapped[bool] = mapped_column(Boolean, default=False)
    rarity_level: Mapped[str] = mapped_column(String(10), default="mid")
    has_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    is_special: Mapped[bool] = mapped_column(Boolean, default=False)
    price_min: Mapped[int] = mapped_column(Integer, default=0)
    price_max: Mapped[int] = mapped_column(Integer, default=0)
    num_performances_candidates: Mapped[list] = mapped_column(JSON, default=list)

    group: Mapped[Group] = relationship(back_populates="productions")
    past_sales: Mapped[list[PastPerformanceSale]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )
    venues: Mapped[list[Venue]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )
    simulation_runs: Mapped[list[SimulationRun]] = relationship(
        back_populates="production", cascade="all, delete-orphan"
    )


class PastPerformanceSale(Base):
    __tablename__ = "past_performance_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    production_id: Mapped[int] = mapped_column(ForeignKey("productions.id"))
    venue_name: Mapped[str] = mapped_column(String(200), default="")
    capacity: Mapped[int] = mapped_column(Integer)
    ticket_price: Mapped[int] = mapped_column(Integer)
    num_performances: Mapped[int] = mapped_column(Integer)
    tickets_sold: Mapped[int] = mapped_column(Integer)
    sold_out: Mapped[bool] = mapped_column(Boolean, default=False)
    days_before_sold_out: Mapped[int | None] = mapped_column(Integer, nullable=True)

    production: Mapped[Production] = relationship(back_populates="past_sales")


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    production_id: Mapped[int] = mapped_column(ForeignKey("productions.id"))
    name: Mapped[str] = mapped_column(String(200))
    area: Mapped[str] = mapped_column(String(100), default="")
    capacity: Mapped[int] = mapped_column(Integer)
    venue_cost: Mapped[int] = mapped_column(Integer, default=0)
    walk_minutes: Mapped[int] = mapped_column(Integer, default=0)
    location_rating: Mapped[int] = mapped_column(Integer, default=3)
    brand_rating: Mapped[int] = mapped_column(Integer, default=3)

    production: Mapped[Production] = relationship(back_populates="venues")
    scenarios: Mapped[list[SimulationScenario]] = relationship(back_populates="venue")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    production_id: Mapped[int] = mapped_column(ForeignKey("productions.id"))
    model_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow
    )
    base_attendance_power: Mapped[float] = mapped_column(Float)
    explanation_json: Mapped[list] = mapped_column(JSON, default=list)

    production: Mapped[Production] = relationship(back_populates="simulation_runs")
    scenarios: Mapped[list[SimulationScenario]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    actual_results: Mapped[list[ActualResult]] = relationship(back_populates="run")


class SimulationScenario(Base):
    __tablename__ = "simulation_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id"))
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"))
    price: Mapped[int] = mapped_column(Integer)
    num_performances: Mapped[int] = mapped_column(Integer)
    expected_demand: Mapped[float] = mapped_column(Float)
    available_seats: Mapped[int] = mapped_column(Integer)
    expected_sold: Mapped[float] = mapped_column(Float)
    occupancy_rate: Mapped[float] = mapped_column(Float)
    revenue: Mapped[float] = mapped_column(Float)
    profit: Mapped[float] = mapped_column(Float)
    venue_fit: Mapped[str] = mapped_column(String(20))
    is_recommended_balance: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recommended_sellout: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recommended_revenue: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recommended_profit: Mapped[bool] = mapped_column(Boolean, default=False)

    run: Mapped[SimulationRun] = relationship(back_populates="scenarios")
    venue: Mapped[Venue] = relationship(back_populates="scenarios")


class ActualResult(Base):
    __tablename__ = "actual_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id"))
    scenario_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulation_scenarios.id"), nullable=True
    )
    actual_price: Mapped[int] = mapped_column(Integer)
    actual_venue_name: Mapped[str] = mapped_column(String(200))
    actual_num_performances: Mapped[int] = mapped_column(Integer)
    actual_tickets_sold: Mapped[int] = mapped_column(Integer)
    actual_occupancy_rate: Mapped[float] = mapped_column(Float)
    actual_sold_out: Mapped[bool] = mapped_column(Boolean, default=False)
    actual_days_before_sold_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_revenue: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    run: Mapped[SimulationRun] = relationship(back_populates="actual_results")
