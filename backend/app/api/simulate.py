from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.calculation import constants as calc_constants
from app.calculation.demand_estimator import RuleBasedDemandEstimator
from app.calculation.recommender import recommend, run_full_search
from app.calculation.simulator import PerformanceSimulator
from app.calculation.types import (
    CurrentProductionInput,
    DemandFeatures,
    Genre,
    GroupInfo,
    PastPerformance,
    RarityLevel,
    VenueCandidate,
)
from app.db import get_db
from app.models import models
from app.schemas.simulate import (
    ActualResultIn,
    ExplanationItemOut,
    ScenarioOut,
    SimulateRequest,
    SimulateResponse,
)

router = APIRouter(prefix="/api", tags=["simulate"])

DISCLAIMER = (
    "本シミュレーションは過去実績と入力条件に基づく参考値です。"
    "実際の販売結果を保証するものではありません。"
)


def _scenario_to_out(s) -> ScenarioOut:
    return ScenarioOut(
        venue_name=s.venue_name,
        price=s.price,
        num_performances=s.num_performances,
        available_seats=s.available_seats,
        expected_demand=s.expected_demand,
        expected_sold=s.expected_sold,
        occupancy_rate=s.occupancy_rate,
        revenue=s.revenue,
        profit=s.profit,
        venue_fit=s.venue_fit.value,
        venue_fit_message=s.venue_fit_message,
    )


@router.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest, db: Session = Depends(get_db)) -> SimulateResponse:
    group_info = GroupInfo(
        name=req.group.name,
        genre=Genre(req.group.genre),
        years_active=req.group.years_active,
        sns_x_followers=req.group.sns_x_followers,
        sns_instagram_followers=req.group.sns_instagram_followers,
        sns_youtube_subscribers=req.group.sns_youtube_subscribers,
        sns_other_followers=req.group.sns_other_followers,
    )
    past_performances = [
        PastPerformance(
            name=p.name,
            performance_date=p.performance_date,
            capacity=p.capacity,
            price=p.price,
            num_performances=p.num_performances,
            tickets_sold=p.tickets_sold,
            sold_out=p.sold_out,
            is_new_work=p.is_new_work,
            is_weekend_holiday=p.is_weekend_holiday,
            is_evening=p.is_evening,
            days_before_sold_out=p.days_before_sold_out,
            prefecture=p.prefecture,
            area=p.area,
            venue_name=p.venue_name,
        )
        for p in req.past_performances
    ]
    current_production = CurrentProductionInput(
        area=req.current_production.area,
        is_new_work=req.current_production.is_new_work,
        is_weekend_holiday=req.current_production.is_weekend_holiday,
        is_evening=req.current_production.is_evening,
        rarity_level=RarityLevel(req.current_production.rarity_level),
        has_guest=req.current_production.has_guest,
        is_special=req.current_production.is_special,
        price_min=req.current_production.price_min,
        price_max=req.current_production.price_max,
        performance_date=req.current_production.performance_date,
    )
    venues = [
        VenueCandidate(
            name=v.name,
            area=v.area,
            capacity=v.capacity,
            venue_cost=v.venue_cost,
            walk_minutes=v.walk_minutes,
            location_rating=v.location_rating,
            brand_rating=v.brand_rating,
        )
        for v in req.venues
    ]

    estimator = RuleBasedDemandEstimator()
    simulator = PerformanceSimulator(estimator)

    base_features = DemandFeatures(
        group=group_info,
        past_performances=past_performances,
        current_production=current_production,
        venue=venues[0],
        price=req.current_production.price_min,
        num_performances=req.num_performances_candidates[0],
    )
    # 説明可能性・基礎集客力の表示用に、最初の会場・最低価格の estimate を代表値として使う
    reference_estimate = estimator.estimate_demand(base_features)

    scenarios = run_full_search(
        simulator,
        base_features,
        venues,
        req.num_performances_candidates,
        req.current_production.price_min,
        req.current_production.price_max,
    )
    recommendation = recommend(scenarios, reference_estimate.baseline_price)

    # --- 永続化 ---
    group_row = models.Group(
        name=group_info.name,
        genre=group_info.genre.value,
        years_active=group_info.years_active,
        sns_x_followers=group_info.sns_x_followers,
        sns_instagram_followers=group_info.sns_instagram_followers,
        sns_youtube_subscribers=group_info.sns_youtube_subscribers,
        sns_other_followers=group_info.sns_other_followers,
    )
    db.add(group_row)
    db.flush()

    production_row = models.Production(
        group_id=group_row.id,
        is_past=False,
        area=current_production.area,
        performance_date=current_production.performance_date,
        is_new_work=current_production.is_new_work,
        is_weekend_holiday=current_production.is_weekend_holiday,
        is_evening=current_production.is_evening,
        rarity_level=current_production.rarity_level.value,
        has_guest=current_production.has_guest,
        is_special=current_production.is_special,
        price_min=current_production.price_min,
        price_max=current_production.price_max,
        num_performances_candidates=req.num_performances_candidates,
    )
    db.add(production_row)
    db.flush()

    for p in past_performances:
        db.add(
            models.PastPerformanceSale(
                production_id=production_row.id,
                venue_name=p.venue_name,
                capacity=p.capacity,
                ticket_price=p.price,
                num_performances=p.num_performances,
                tickets_sold=p.tickets_sold,
                sold_out=p.sold_out,
                days_before_sold_out=p.days_before_sold_out,
            )
        )

    venue_rows: dict[str, models.Venue] = {}
    for v in venues:
        row = models.Venue(
            production_id=production_row.id,
            name=v.name,
            area=v.area,
            capacity=v.capacity,
            venue_cost=v.venue_cost,
            walk_minutes=v.walk_minutes,
            location_rating=v.location_rating,
            brand_rating=v.brand_rating,
        )
        db.add(row)
        venue_rows[v.name] = row
    db.flush()

    run_row = models.SimulationRun(
        production_id=production_row.id,
        model_version=calc_constants.MODEL_VERSION,
        base_attendance_power=reference_estimate.base_attendance_power,
        explanation_json=[e.__dict__ for e in reference_estimate.explanation],
    )
    db.add(run_row)
    db.flush()

    for s in scenarios:
        db.add(
            models.SimulationScenario(
                run_id=run_row.id,
                venue_id=venue_rows[s.venue_name].id,
                price=s.price,
                num_performances=s.num_performances,
                expected_demand=s.expected_demand,
                available_seats=s.available_seats,
                expected_sold=s.expected_sold,
                occupancy_rate=s.occupancy_rate,
                revenue=s.revenue,
                profit=s.profit,
                venue_fit=s.venue_fit.value,
                is_recommended_balance=(s is recommendation.balance_scenario),
                is_recommended_sellout=(s is recommendation.sellout_scenario),
                is_recommended_revenue=(s is recommendation.revenue_scenario),
                is_recommended_profit=(s is recommendation.profit_scenario),
            )
        )
    db.commit()

    return SimulateResponse(
        run_id=run_row.id,
        model_version=calc_constants.MODEL_VERSION,
        base_attendance_power=reference_estimate.base_attendance_power,
        baseline_price=reference_estimate.baseline_price,
        recommended_price_range=recommendation.recommended_price_range,
        balance_price=recommendation.balance_price,
        sellout_price=recommendation.sellout_price,
        revenue_price=recommendation.revenue_price,
        profit_price=recommendation.profit_price,
        balance_scenario=_scenario_to_out(recommendation.balance_scenario),
        sellout_scenario=_scenario_to_out(recommendation.sellout_scenario),
        revenue_scenario=_scenario_to_out(recommendation.revenue_scenario),
        profit_scenario=_scenario_to_out(recommendation.profit_scenario),
        scenarios=[_scenario_to_out(s) for s in scenarios],
        explanation=[
            ExplanationItemOut(factor=e.factor, multiplier=e.multiplier, description=e.description)
            for e in reference_estimate.explanation
        ],
        disclaimer=DISCLAIMER,
    )


@router.post("/actual_results")
def create_actual_result(payload: ActualResultIn, db: Session = Depends(get_db)) -> dict:
    run = db.get(models.SimulationRun, payload.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="simulation_run not found")

    available_seats = None
    if payload.actual_capacity:
        available_seats = payload.actual_capacity * payload.actual_num_performances
    elif payload.scenario_id is not None:
        scenario = db.get(models.SimulationScenario, payload.scenario_id)
        if scenario is not None:
            available_seats = scenario.available_seats
    occupancy = (
        payload.actual_tickets_sold / available_seats
        if available_seats and available_seats > 0
        else 0.0
    )
    row = models.ActualResult(
        run_id=payload.run_id,
        scenario_id=payload.scenario_id,
        actual_price=payload.actual_price,
        actual_venue_name=payload.actual_venue_name,
        actual_num_performances=payload.actual_num_performances,
        actual_tickets_sold=payload.actual_tickets_sold,
        actual_occupancy_rate=occupancy,
        actual_sold_out=payload.actual_sold_out,
        actual_days_before_sold_out=payload.actual_days_before_sold_out,
        actual_revenue=payload.actual_price * payload.actual_tickets_sold,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "run_id": row.run_id}
