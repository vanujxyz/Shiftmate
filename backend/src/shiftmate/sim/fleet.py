"""Build the simulated fleet: machines, operators and their (hidden) personalities (TRD §7.1, §7.3).

- Machines are numbered per type in `fleet.site_order` (so EXC001 is in Chennai and WHL014 in
  Pilbara). Model year is random; the sensor tier follows the year (< 2016 basic, 2016–2021
  standard, ≥ 2022 advanced) with a 10 % chance of one tier lower (missing retrofit). Fixed
  machines from config (EXC001, WHL014) override the random draw.
- Engine hours at the start grow with machine age.
- Operators get site-appropriate names, a language from the site's languages, experience,
  certifications that cover the site's machine types, and a usual machine.
- Personalities: about 15 % of operators have one elevated trait (> 0.6); the rest are low. Skill
  comes from experience plus noise. Personalities are returned separately and never stored with
  the public operator record (golden rule 5).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.schema.enums import Language, MachineType, SensorTier
from shiftmate.schema.reference import Machine, Operator
from shiftmate.sim.params import TRAITS, Personality

TYPE_ORDER = (MachineType.EXCAVATOR, MachineType.WHEEL_LOADER, MachineType.DOZER)
LANGUAGE_WEIGHTS = (0.7, 0.2, 0.1)  # first listed site language is most common
DEMO_YEAR = 2026


@dataclass
class Fleet:
    machines: list[Machine]
    operators: list[Operator]
    personalities: dict[str, Personality]  # simulator-only
    usual_machine: dict[str, str | None]  # operator_id → machine_id

    def machines_at(self, site_id: str) -> list[Machine]:
        return [m for m in self.machines if m.site_id == site_id]

    def operators_at(self, site_id: str) -> list[Operator]:
        return [o for o in self.operators if o.home_site_id == site_id]


def _tier_for_year(cfg: ShiftMateConfig, year: int) -> SensorTier:
    p = cfg.simulator.fleet
    if year < p.basic_before_year:
        return SensorTier.BASIC
    if year < p.advanced_from_year:
        return SensorTier.STANDARD
    return SensorTier.ADVANCED


def _downgrade(tier: SensorTier) -> SensorTier:
    return {
        SensorTier.ADVANCED: SensorTier.STANDARD,
        SensorTier.STANDARD: SensorTier.BASIC,
        SensorTier.BASIC: SensorTier.BASIC,
    }[tier]


def build_machines(cfg: ShiftMateConfig, rng: np.random.Generator) -> list[Machine]:
    p = cfg.simulator.fleet
    fixed = {m.machine_id: m for m in p.fixed_machines}
    counters = dict.fromkeys(TYPE_ORDER, 0)
    machines: list[Machine] = []
    for site_id in p.site_order:
        site = cfg.sites[site_id]
        for machine_type in TYPE_ORDER:
            profile = cfg.profiles[machine_type]
            for _ in range(site.fleet.count(machine_type)):
                counters[machine_type] += 1
                machine_id = f"{profile.id_prefix}{counters[machine_type]:03d}"
                # Draw every random value even for fixed machines, so the stream stays aligned.
                year = int(rng.integers(int(p.model_year.min), int(p.model_year.max) + 1))
                model = str(rng.choice(profile.example_models))
                tier = _tier_for_year(cfg, year)
                if rng.random() < p.tier_downgrade_prob:
                    tier = _downgrade(tier)
                age_hours = (DEMO_YEAR - year) * 1400 + rng.normal(0, 600)
                hours = float(
                    np.clip(age_hours, p.engine_hours_start.min, p.engine_hours_start.max)
                )
                if machine_id in fixed:
                    f = fixed[machine_id]
                    if f.site_id != site_id:
                        raise ValueError(f"fixed machine {machine_id} is not at {f.site_id}")
                    year, model, tier, hours = (
                        f.model_year,
                        f.model,
                        f.sensor_tier,
                        f.engine_hours_start,
                    )
                machines.append(
                    Machine(
                        machine_id=machine_id,
                        machine_type=machine_type,
                        model=model,
                        model_year=year,
                        sensor_tier=tier,
                        site_id=site_id,
                        engine_hours_start=round(hours, 1),
                    )
                )
    return machines


def _personality(cfg: ShiftMateConfig, experience: float, rng: np.random.Generator) -> Personality:
    p = cfg.simulator.operators
    traits = {t: float(rng.uniform(p.normal_trait.min, p.normal_trait.max)) for t in TRAITS}
    if rng.random() < p.elevated_trait_share:
        chosen = TRAITS[int(rng.integers(0, len(TRAITS)))]
        traits[chosen] = float(rng.uniform(p.elevated_trait.min, p.elevated_trait.max))
    skill = 1 + (experience - 8) * p.skill_per_experience_year + rng.normal(0, p.skill_noise_sd)
    return Personality(**traits, skill=float(np.clip(skill, 0.8, 1.2)))


def build_fleet(cfg: ShiftMateConfig, rng: np.random.Generator) -> Fleet:
    machines = build_machines(cfg, rng)
    p = cfg.simulator.operators
    fixed_ops = {f.operator_id: f for f in p.fixed}
    operators: list[Operator] = []
    personalities: dict[str, Personality] = {}
    usual: dict[str, str | None] = {}
    next_id = p.first_id
    for site_id in cfg.simulator.fleet.site_order:
        site = cfg.sites[site_id]
        site_machines = [m for m in machines if m.site_id == site_id]
        weights = np.array(LANGUAGE_WEIGHTS[: len(site.languages)], dtype=float)
        weights /= weights.sum()
        # machine types in proportion to the fleet, so every machine type has certified operators
        type_pool = [m.machine_type for m in site_machines]
        for index in range(site.operators):
            operator_id = f"OP{next_id}"
            next_id += 1
            experience = float(
                np.round(rng.uniform(p.experience_years.min, p.experience_years.max), 1)
            )
            language = Language(site.languages[int(rng.choice(len(site.languages), p=weights))])
            primary = type_pool[index % len(type_pool)]
            certs = {primary}
            if rng.random() < 0.4:
                certs.add(TYPE_ORDER[int(rng.integers(0, len(TYPE_ORDER)))])
            personality = _personality(cfg, experience, rng)
            name = site.operator_names[index]
            machine_for = site_machines[index].machine_id if index < len(site_machines) else None
            if operator_id in fixed_ops:
                f = fixed_ops[operator_id]
                name, language, experience = f.name, f.preferred_language, f.experience_years
                personality, machine_for = f.personality, f.machine_id
                fixed_type = next(m.machine_type for m in machines if m.machine_id == f.machine_id)
                certs = {fixed_type}
            operators.append(
                Operator(
                    operator_id=operator_id,
                    name=name,
                    preferred_language=language,
                    experience_years=experience,
                    home_site_id=site_id,
                    certifications=sorted(certs, key=TYPE_ORDER.index),
                )
            )
            personalities[operator_id] = personality
            usual[operator_id] = machine_for
    # The usual machine must match a certification.
    by_id = {m.machine_id: m for m in machines}
    for op in operators:
        machine_id = usual[op.operator_id]
        if machine_id and by_id[machine_id].machine_type not in op.certifications:
            op.certifications.append(by_id[machine_id].machine_type)
    return Fleet(machines, operators, personalities, usual)
