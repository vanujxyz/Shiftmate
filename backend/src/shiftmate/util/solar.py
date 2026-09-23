"""Simplified sunrise and sunset from latitude and day of year (TRD §7.2).

Solar declination: δ = 23.44° · sin(360/365 · (day − 81)).
Half day length (hour angle): ω₀ = arccos(−tan φ · tan δ), clamped for polar day and night.
Sunrise/sunset = solar noon ∓ ω₀/15 hours. Good to a few minutes, which is all a site needs.
"""

import math
from datetime import time


def day_length_hours(latitude_deg: float, day_of_year: int) -> float:
    declination = math.radians(23.44) * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
    x = -math.tan(math.radians(latitude_deg)) * math.tan(declination)
    if x >= 1:
        return 0.0  # polar night
    if x <= -1:
        return 24.0  # midnight sun
    return 2 * math.degrees(math.acos(x)) / 15


def sun_times_minutes(
    latitude_deg: float, day_of_year: int, solar_noon: time
) -> tuple[float, float]:
    """Sunrise and sunset as minutes after local midnight (may equal each other in polar night)."""
    noon = solar_noon.hour * 60 + solar_noon.minute
    half = day_length_hours(latitude_deg, day_of_year) * 30  # minutes
    return noon - half, noon + half


def is_night(minute_of_day: float, sunrise_min: float, sunset_min: float) -> bool:
    return not (sunrise_min <= minute_of_day < sunset_min)
