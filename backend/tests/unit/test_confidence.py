from app.calculation.confidence import (
    DataSufficiencyLevel,
    assess_recommendation_reliability,
    classify_data_sufficiency,
)


def test_classify_data_sufficiency_thresholds():
    assert classify_data_sufficiency(0) == DataSufficiencyLevel.LOW
    assert classify_data_sufficiency(1) == DataSufficiencyLevel.LOW
    assert classify_data_sufficiency(2) == DataSufficiencyLevel.MEDIUM
    assert classify_data_sufficiency(3) == DataSufficiencyLevel.NORMAL
    assert classify_data_sufficiency(10) == DataSufficiencyLevel.NORMAL


def test_low_confidence_with_boundary_hit_disallows_strong_recommendation():
    reliability = assess_recommendation_reliability(
        usable_history_count=1, balanced_price=14400, price_min=4000, price_max=14400
    )
    assert reliability.data_sufficiency == DataSufficiencyLevel.LOW
    assert reliability.price_search_boundary_hit is True
    assert reliability.is_strong_recommendation_allowed is False
    assert len(reliability.warnings) >= 2


def test_normal_confidence_without_boundary_hit_has_no_warnings():
    reliability = assess_recommendation_reliability(
        usable_history_count=4, balanced_price=7700, price_min=4000, price_max=14400
    )
    assert reliability.data_sufficiency == DataSufficiencyLevel.NORMAL
    assert reliability.price_search_boundary_hit is False
    assert reliability.is_strong_recommendation_allowed is True
    assert reliability.warnings == []


def test_reliability_never_changes_the_recommended_price_itself():
    """confidence評価はガードレール(警告)のみであり、価格そのものをclampしない。"""
    reliability = assess_recommendation_reliability(
        usable_history_count=1, balanced_price=14400, price_min=4000, price_max=14400
    )
    # balanced_priceは引数として渡した値のまま、reliability側で書き換えられるフィールドがない
    assert not hasattr(reliability, "balanced_price")


def test_normal_confidence_with_boundary_hit_still_warns_but_allows_strong_recommendation():
    reliability = assess_recommendation_reliability(
        usable_history_count=5, balanced_price=4000, price_min=4000, price_max=14400
    )
    assert reliability.data_sufficiency == DataSufficiencyLevel.NORMAL
    assert reliability.is_strong_recommendation_allowed is True
    assert len(reliability.warnings) == 1  # 境界張り付きの情報のみ(無警告にはしない)
