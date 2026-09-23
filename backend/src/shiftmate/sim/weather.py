"""Site weather, ground condition and daylight (TRD §7.2).

How one day is generated (hourly, then spread to minutes):
- Temperature = month mean + amplitude · sin(daily cycle peaking at 15:00) + AR(1) noise.
- Humidity moves opposite to temperature (drier in the afternoon heat) plus noise.
- Rain is a two-state Markov chain per hour (dry → rain with the month's probability, rain → dry
  with `rain_stop_prob`); a rainy hour's intensity is exponential around the month's mean.
- Heat index uses the NWS Rothfusz regression (util/heat_index.py).
- Ground: ≥ 2 mm in 2 h → wet; ≥ 10 mm in 6 h → muddy; it dries one step after 6 dry hours
  (longer when cold); below 0 °C it is frozen; otherwise the site's baseline (dry or rocky).
- Visibility falls with rain intensity, and during dust (Pilbara) or fog (Tromsø) events.
- Night comes from sunrise/sunset for the site latitude and the season's month (D-016).

State (temperature anomaly, rain, wetness) carries over from one day to the next, so a wet
evening gives a wet next morning. Deterministic for a given generator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from shiftmate.schema.config import MonthProfile, Site
from shiftmate.schema.enums import GroundCondition
from shiftmate.sim.params import WeatherParams
from shiftmate.util.heat_index import heat_index_c
from shiftmate.util.solar import sun_times_minutes

MINUTES_PER_DAY = 1440
PEAK_HOUR = 15.0


@dataclass
class DayWeather:
    """Minute-by-minute conditions for one site-day (index = minute after local midnight)."""

    temp_c: np.ndarray
    rh_pct: np.ndarray
    heat_index_c: np.ndarray
    precip_mm_h: np.ndarray
    wind_kmh: np.ndarray
    visibility_m: np.ndarray
    is_night: np.ndarray
    ground: list[GroundCondition]  # per minute
    sunrise_min: float
    sunset_min: float

    def at(self, minute: float) -> dict[str, object]:
        i = int(min(max(minute, 0), MINUTES_PER_DAY - 1))
        return {
            "ambient_temp_c": float(self.temp_c[i]),
            "relative_humidity_pct": float(self.rh_pct[i]),
            "heat_index_c": float(self.heat_index_c[i]),
            "precipitation_mm_h": float(self.precip_mm_h[i]),
            "wind_kmh": float(self.wind_kmh[i]),
            "visibility_m": float(self.visibility_m[i]),
            "is_night": bool(self.is_night[i]),
            "ground_condition": self.ground[i],
        }


@dataclass
class WeatherState:
    temp_anomaly: float = 0.0
    raining: bool = False
    rain_history_mm: list[float] = field(default_factory=lambda: [0.0] * 6)  # last 6 hours
    dry_hours: float = 24.0
    ground: GroundCondition | None = None
    event_hours_left: int = 0
    event_visibility_m: float = 0.0


class WeatherModel:
    def __init__(self, site: Site, params: WeatherParams) -> None:
        self.site = site
        self.p = params
        self.state = WeatherState(ground=site.ground_baseline)

    def _baseline(self) -> GroundCondition:
        return self.site.ground_baseline

    def _next_ground(self, temp_c: float, rain_mm: float) -> GroundCondition:
        s = self.state
        s.rain_history_mm = [*s.rain_history_mm[1:], rain_mm]
        s.dry_hours = 0.0 if rain_mm > 0 else s.dry_hours + 1
        rain_2h = sum(s.rain_history_mm[-2:])
        rain_6h = sum(s.rain_history_mm)
        current = s.ground or self._baseline()
        if temp_c < 0:
            new = GroundCondition.FROZEN
        elif rain_6h >= self.p.muddy_mm_in_6h:
            new = GroundCondition.MUDDY
        elif rain_2h >= self.p.wet_mm_in_2h and current != GroundCondition.MUDDY:
            new = GroundCondition.WET
        else:
            new = current
            if current == GroundCondition.FROZEN:
                new = GroundCondition.WET  # thawing ground is wet
            dry_needed = self.p.dry_after_h if temp_c >= 15 else self.p.dry_after_h_cold
            if s.dry_hours >= dry_needed:
                if current == GroundCondition.MUDDY:
                    new = GroundCondition.WET
                    s.dry_hours = 0.0  # another drying period to reach the baseline
                elif current == GroundCondition.WET:
                    new = self._baseline()
        s.ground = new
        return new

    def generate_day(
        self,
        day: date,
        month: MonthProfile,
        daylight_day_of_year: int,
        rng: np.random.Generator,
    ) -> DayWeather:
        p, s = self.p, self.state
        hours = np.arange(24)
        # temperature: daily cycle + AR(1) anomaly
        temps, rhs, rains, winds, visibility, grounds = [], [], [], [], [], []
        for h in hours:
            s.temp_anomaly = p.temp_ar1_phi * s.temp_anomaly + rng.normal(0, p.temp_noise_sd)
            cycle = math.sin(2 * math.pi * (h - PEAK_HOUR + 6) / 24)  # peak at 15:00
            temp = month.temp_mean_c + month.temp_amp_c * cycle + s.temp_anomaly
            # rain Markov chain
            if s.raining:
                s.raining = rng.random() >= p.rain_stop_prob
            else:
                s.raining = rng.random() < month.rain_prob
            rain = float(rng.exponential(month.rain_mean_mm_h)) if s.raining else 0.0
            if s.raining:
                temp -= 1.5  # rain cools the air a little
            rh = month.rh_mean + p.rh_per_c_above_mean * (temp - month.temp_mean_c)
            rh += rng.normal(0, p.rh_noise_sd) + (12 if s.raining else 0)
            rh = float(np.clip(rh, 8, 100))
            wind = max(0.0, month.wind_mean_kmh + rng.normal(0, p.wind_sd_kmh))
            # visibility: rain, plus dust or fog events that last a few hours
            if s.event_hours_left <= 0:
                if rng.random() < month.dust_event_prob:
                    s.event_hours_left = int(rng.integers(p.dust_hours.min, p.dust_hours.max + 1))
                    s.event_visibility_m = float(
                        rng.uniform(p.dust_visibility_m.min, p.dust_visibility_m.max)
                    )
                elif rng.random() < month.fog_prob:
                    s.event_hours_left = int(rng.integers(p.fog_hours.min, p.fog_hours.max + 1))
                    s.event_visibility_m = float(
                        rng.uniform(p.fog_visibility_m.min, p.fog_visibility_m.max)
                    )
            vis = p.clear_visibility_m / (1 + p.rain_visibility_factor * rain)
            if s.event_hours_left > 0:
                vis = min(vis, s.event_visibility_m)
                s.event_hours_left -= 1
            temps.append(temp)
            rhs.append(rh)
            rains.append(rain)
            winds.append(wind)
            visibility.append(vis)
            grounds.append(self._next_ground(temp, rain))

        minutes = np.arange(MINUTES_PER_DAY)
        hour_pos = minutes / 60.0
        temp_m = np.interp(hour_pos, hours, temps)
        rh_m = np.interp(hour_pos, hours, rhs)
        hour_idx = np.minimum(minutes // 60, 23)
        rain_m = np.asarray(rains)[hour_idx]
        wind_m = np.asarray(winds)[hour_idx]
        vis_m = np.asarray(visibility)[hour_idx]
        hi_m = np.array([heat_index_c(t, r) for t, r in zip(temp_m, rh_m, strict=True)])
        sunrise, sunset = sun_times_minutes(self.site.latitude, daylight_day_of_year, p.solar_noon)
        night = (minutes < sunrise) | (minutes >= sunset)
        ground_m = [grounds[h] for h in hour_idx]
        return DayWeather(
            temp_c=np.round(temp_m, 2),
            rh_pct=np.round(rh_m, 1),
            heat_index_c=hi_m,
            precip_mm_h=np.round(rain_m, 2),
            wind_kmh=np.round(wind_m, 1),
            visibility_m=np.round(vis_m, 0),
            is_night=night,
            ground=ground_m,
            sunrise_min=sunrise,
            sunset_min=sunset,
        )
