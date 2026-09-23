"""Working-conditions risk level (TRD §4.5, §6.3; PRD F-SAFE-04, F-SAFE-05).

Score = sum of points from each condition, capped at 100:
heat index, rain, ground, darkness, visibility, continuous operation, people nearby, seatbelt off
while working, and near-misses in the last 24 h. Every table of points is in `risk_model.yaml`.

Band: green 0–39, amber 40–69, red 70–100. Going *up* a band is immediate; going *down* needs
the score to stay below the current band's floor for 120 s (hysteresis), so the band does not
flicker when a value hovers at a boundary.

Effective thresholds (used by the Safety engine): proximity distances are the machine profile's
distances × the band's proximity factor (1.0 / 1.25 / 1.5), and fatigue minutes are the profile's
minutes ÷ the band's fatigue factor, divided again by 1.5 when the heat index is ≥ 41 °C. So
conditions visibly tighten safety (PRD principle 5).

The people-nearby component uses the previous tick's thresholds to classify proximity, which
avoids a circular dependency (thresholds depend on the band, the band on proximity).
Pure: no clock reads; time comes in with each update.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from shiftmate.schema.config import Band, MachineProfile, RiskModelConfig
from shiftmate.schema.enums import GroundCondition, ProximityTier, RiskBand

BAND_ORDER = (RiskBand.GREEN, RiskBand.AMBER, RiskBand.RED)


@dataclass(frozen=True)
class RiskInputs:
    heat_index_c: float
    precipitation_mm_h: float
    ground_condition: GroundCondition
    is_night: bool
    visibility_m: float
    continuous_operation_min: float
    proximity_m: float | None
    seatbelt_unfastened_while_working: bool
    near_misses_last_24h: int


@dataclass(frozen=True)
class Thresholds:
    caution_m: float
    danger_m: float
    critical_m: float
    fatigue_warn_min: float
    fatigue_limit_min: float


@dataclass(frozen=True)
class RiskOutput:
    score: int
    band: RiskBand
    band_rank: int
    components: dict[str, int]
    top: list[tuple[str, int]]  # largest contributors, for "Heat +25, Fatigue +10"
    thresholds: Thresholds
    proximity_tier: ProximityTier
    publish: bool  # score moved ≥ 3 or band changed
    band_changed: bool


def banded_points(bands: list[Band], value: float) -> int:
    for band in bands:
        if band.lt is not None and value < band.lt:
            return band.points
        if band.gte is not None and value >= band.gte:
            return band.points
    return 0


def proximity_tier(distance_m: float | None, t: Thresholds) -> ProximityTier:
    if distance_m is None:
        return ProximityTier.CLEAR
    if distance_m <= t.critical_m:
        return ProximityTier.CRITICAL
    if distance_m <= t.danger_m:
        return ProximityTier.DANGER
    if distance_m <= t.caution_m:
        return ProximityTier.CAUTION
    return ProximityTier.CLEAR


class RiskEngine:
    def __init__(self, model: RiskModelConfig, profile: MachineProfile) -> None:
        self.model = model
        self.profile = profile
        self.band = RiskBand.GREEN
        self.below_floor_since: datetime | None = None
        self.last_published: int | None = None
        self.thresholds = self._thresholds(RiskBand.GREEN, heat_index_c=0.0)

    def _band_for(self, score: int) -> RiskBand:
        for band in BAND_ORDER:
            lo, hi = self.model.bands[band]
            if lo <= score <= hi:
                return band
        return RiskBand.RED

    def _thresholds(self, band: RiskBand, heat_index_c: float) -> Thresholds:
        scale = self.model.threshold_scaling[band]
        divisor = scale.fatigue
        if heat_index_c >= self.model.heat_fatigue_override.heat_index_gte:
            divisor *= self.model.heat_fatigue_override.fatigue_divisor
        prox = self.profile.proximity_m
        unsafe = self.profile.unsafe
        return Thresholds(
            caution_m=prox.caution * scale.proximity,
            danger_m=prox.danger * scale.proximity,
            critical_m=prox.critical * scale.proximity,
            fatigue_warn_min=unsafe.continuous_operation_warn_min / divisor,
            fatigue_limit_min=unsafe.continuous_operation_limit_min / divisor,
        )

    def update(self, ts: datetime, x: RiskInputs) -> RiskOutput:
        c = self.model.components
        tier = proximity_tier(x.proximity_m, self.thresholds)
        components = {
            "heat": banded_points(c.heat_index_c, x.heat_index_c),
            "rain": banded_points(c.precipitation_mm_h, x.precipitation_mm_h),
            "ground": c.ground_condition.get(x.ground_condition, 0),
            "night": c.is_night.get(x.is_night, 0),
            "visibility": banded_points(c.visibility_m, x.visibility_m),
            "fatigue": banded_points(c.continuous_operation_min, x.continuous_operation_min),
            "proximity": c.proximity_state.get(tier, 0),
            "seatbelt": c.seatbelt_unfastened_while_working.get(
                x.seatbelt_unfastened_while_working, 0
            ),
            "near_miss": min(
                c.near_miss_last_24h.max, c.near_miss_last_24h.per_event * x.near_misses_last_24h
            ),
        }
        score = min(self.model.max_score, sum(components.values()))
        target = self._band_for(score)
        previous = self.band
        if BAND_ORDER.index(target) > BAND_ORDER.index(self.band):
            self.band = target  # up: immediately
            self.below_floor_since = None
        elif BAND_ORDER.index(target) < BAND_ORDER.index(self.band):
            # down: only after staying below the current band's floor for the hysteresis time
            if self.below_floor_since is None:
                self.below_floor_since = ts
            if (ts - self.below_floor_since).total_seconds() >= self.model.hysteresis_down_s:
                self.band = target
                self.below_floor_since = None
        else:
            self.below_floor_since = None
        band_changed = self.band != previous
        self.thresholds = self._thresholds(self.band, x.heat_index_c)
        publish = (
            band_changed
            or self.last_published is None
            or abs(score - self.last_published) >= self.model.publish_min_delta
        )
        if publish:
            self.last_published = score
        top = sorted(((k, v) for k, v in components.items() if v > 0), key=lambda kv: -kv[1])
        return RiskOutput(
            score=score,
            band=self.band,
            band_rank=BAND_ORDER.index(self.band),
            components=components,
            top=top[: self.model.top_contributors],
            thresholds=self.thresholds,
            proximity_tier=proximity_tier(x.proximity_m, self.thresholds),
            publish=publish,
            band_changed=band_changed,
        )
