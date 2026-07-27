from app.calculation.types import VenueFitCategory
from app.calculation.venue_fit import classify_venue_fit


def test_too_small_when_occupancy_at_or_above_full():
    category, message = classify_venue_fit(1.05)
    assert category == VenueFitCategory.TOO_SMALL
    assert "小さすぎる" in message


def test_good_within_target_band():
    category, _ = classify_venue_fit(0.85)
    assert category == VenueFitCategory.GOOD


def test_slightly_large_below_good_band():
    category, _ = classify_venue_fit(0.60)
    assert category == VenueFitCategory.SLIGHTLY_LARGE


def test_too_large_with_low_occupancy_shows_risk_warning():
    category, message = classify_venue_fit(0.30)
    assert category == VenueFitCategory.TOO_LARGE
    assert "大きすぎる" in message
