"""Load and validate every file in `config/` at start-up (TRD §4).

Each file is parsed with its pydantic model (unknown keys and bad values fail), then cross-file
checks run: lesson triggers must be a known vocabulary word, rule signals must exist in some
sensor tier, referenced lesson and rule ids must exist, and so on. Any problem raises
`ConfigError` naming the file, so a bad config fails fast with a clear message.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from shiftmate.schema.config import (
    AlertPolicyConfig,
    AnomalyConfig,
    ChecklistConfig,
    EdgeConfig,
    EstimationConfig,
    FleetConfig,
    IdleRulesConfig,
    IntentsConfig,
    LessonsConfig,
    MachineProfile,
    PrivacyConfig,
    ReportKeywords,
    RiskModelConfig,
    SafetyRulesConfig,
    SensorTiersConfig,
    Site,
)
from shiftmate.schema.enums import (
    ConditionFlag,
    IdleReason,
    MachineType,
    Priority,
    SensorTier,
)
from shiftmate.settings import REPO_ROOT
from shiftmate.sim.params import SimulatorConfig

REQUIRED_LESSONS = {
    "L-SHUTDOWN",
    "L-IDLE-FUEL",
    "L-SEATBELT",
    "L-SWING-ZONE",
    "L-SPOTTER-SIGNALS",
    "L-HEAT-STRESS",
    "L-WET-GROUND",
    "L-NIGHT-WORK",
    "L-TRUCK-LOADING-FLOW",
    "L-WALKAROUND",
    "L-FATIGUE",
    "D-HAZARD-DRILL-1",
}
KEYWORDS_DIR = REPO_ROOT / "backend" / "src" / "shiftmate" / "assistant" / "keywords"
INTENTS_FILE = KEYWORDS_DIR / "intents.yaml"
REPORTS_FILE = KEYWORDS_DIR / "reports.yaml"


class ConfigError(Exception):
    """A config file is missing, malformed or inconsistent with another file."""


@dataclass(frozen=True)
class ShiftMateConfig:
    profiles: dict[MachineType, MachineProfile]
    sensor_tiers: SensorTiersConfig
    sites: dict[str, Site]
    safety_rules: SafetyRulesConfig
    risk_model: RiskModelConfig
    alert_policy: AlertPolicyConfig
    idle_rules: IdleRulesConfig
    privacy: PrivacyConfig
    anomaly: AnomalyConfig
    estimation: EstimationConfig
    lessons: LessonsConfig
    checklist: ChecklistConfig
    intents: IntentsConfig
    report_keywords: ReportKeywords
    edge: EdgeConfig
    fleet: FleetConfig
    simulator: SimulatorConfig  # read only by shiftmate.sim

    def lesson_trigger_vocabulary(self) -> set[str]:
        return (
            {r.value for r in IdleReason}
            | {rule.id for rule in self.safety_rules.rules}
            | set(self.anomaly.codes())
            | {f.value for f in ConditionFlag}
        )

    def all_signals(self) -> set[str]:
        return set().union(*(self.sensor_tiers.signals_for(t) for t in SensorTier))


def _read_yaml(path: Path) -> object:
    if not path.exists():
        raise ConfigError(f"{path}: file not found")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc


def _parse[M: BaseModel](path: Path, model: type[M]) -> M:
    try:
        return model.model_validate(_read_yaml(path))
    except ValidationError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def _cross_check(cfg: ShiftMateConfig) -> None:
    problems: list[str] = []

    # machine profiles
    for machine_type in MachineType:
        if machine_type not in cfg.profiles:
            problems.append(f"machine_profiles: missing profile for {machine_type}")

    # safety rules: signals must exist in some tier
    known_signals = cfg.all_signals()
    for rule in cfg.safety_rules.rules:
        for signal in rule.requires_signals:
            if signal not in known_signals:
                problems.append(f"safety_rules: {rule.id} requires unknown signal '{signal}'")

    # safety rules: every expression compiles with the safe evaluator (no eval, known names only)
    from shiftmate.engines.rule_eval import RuleError, compile_rule
    from shiftmate.engines.safety import CONTEXT_NAMES

    for rule in cfg.safety_rules.rules:
        try:
            compile_rule(rule.when, CONTEXT_NAMES)
        except RuleError as exc:
            problems.append(f"safety_rules: {rule.id}: {exc}")

    # alert policy: rule ids shown in the rail must exist
    rule_ids = {rule.id for rule in cfg.safety_rules.rules}
    for rule_id in cfg.alert_policy.live_in_rail_while_working:
        if rule_id not in rule_ids:
            problems.append(f"alert_policy: live_in_rail_while_working has unknown rule {rule_id}")

    # lessons: required ids, unique ids, trigger vocabulary
    lesson_ids = [lesson.id for lesson in cfg.lessons.lessons]
    if len(lesson_ids) != len(set(lesson_ids)):
        problems.append("lessons: lesson ids must be unique")
    missing = REQUIRED_LESSONS - set(lesson_ids)
    if missing:
        problems.append(f"lessons: missing required lessons {sorted(missing)}")
    vocabulary = cfg.lesson_trigger_vocabulary()
    for lesson in cfg.lessons.lessons:
        for trigger in lesson.triggers:
            if trigger not in vocabulary:
                problems.append(f"lessons: {lesson.id} has unknown trigger '{trigger}'")

    # idle responses: referenced lessons exist
    for reason, response in cfg.idle_rules.responses.items():
        if response.lesson and response.lesson not in lesson_ids:
            problems.append(f"idle_rules: {reason} refers to unknown lesson {response.lesson}")

    # privacy: detail list uses known words
    privacy_words = (
        {p.value for p in Priority}
        | {"incident", "near_miss"}
        | {r.value for r in IdleReason}
        | rule_ids
    )
    for word in cfg.privacy.supervisor_sees_operator_detail_for:
        if word not in privacy_words:
            problems.append(
                f"privacy: unknown entry '{word}' in supervisor_sees_operator_detail_for"
            )

    # estimation: reasons refer to model features
    for feature in cfg.estimation.reason_keys:
        if feature not in cfg.estimation.features:
            problems.append(f"estimation: reason_keys has unknown feature '{feature}'")
    for feature in cfg.estimation.categorical:
        if feature not in cfg.estimation.features:
            problems.append(f"estimation: categorical feature '{feature}' is not a feature")

    # sites: enough names for the operators; zone types a site needs
    for site in cfg.sites.values():
        if len(site.operator_names) < site.operators:
            problems.append(f"sites: {site.site_id} lists fewer names than operators")
        zone_types = {zone.type.value for zone in site.layout.zones}
        for needed in ("dig", "loading", "haul_road", "break_area"):
            if needed not in zone_types:
                problems.append(f"sites: {site.site_id} has no {needed} zone")

    if problems:
        raise ConfigError("Config cross-checks failed:\n  - " + "\n  - ".join(problems))


def load_config(config_dir: Path | None = None) -> ShiftMateConfig:
    """Load, validate and cross-check the whole config. Raises ConfigError on any problem."""
    root = config_dir or (REPO_ROOT / "config")
    profiles: dict[MachineType, MachineProfile] = {}
    for path in sorted((root / "machine_profiles").glob("*.yaml")):
        profile = _parse(path, MachineProfile)
        if path.stem != profile.machine_type.value:
            raise ConfigError(f"{path}: file name must match machine_type '{profile.machine_type}'")
        profiles[profile.machine_type] = profile

    sites: dict[str, Site] = {}
    for path in sorted((root / "sites").glob("*.yaml")):
        site = _parse(path, Site)
        if site.site_id in sites:
            raise ConfigError(f"{path}: duplicate site_id {site.site_id}")
        sites[site.site_id] = site
    if not sites:
        raise ConfigError(f"{root / 'sites'}: no site files found")

    cfg = ShiftMateConfig(
        profiles=profiles,
        sensor_tiers=_parse(root / "sensor_tiers.yaml", SensorTiersConfig),
        sites=sites,
        safety_rules=_parse(root / "safety_rules.yaml", SafetyRulesConfig),
        risk_model=_parse(root / "risk_model.yaml", RiskModelConfig),
        alert_policy=_parse(root / "alert_policy.yaml", AlertPolicyConfig),
        idle_rules=_parse(root / "idle_rules.yaml", IdleRulesConfig),
        privacy=_parse(root / "privacy.yaml", PrivacyConfig),
        anomaly=_parse(root / "anomaly.yaml", AnomalyConfig),
        estimation=_parse(root / "estimation.yaml", EstimationConfig),
        lessons=_parse(root / "lessons.yaml", LessonsConfig),
        checklist=_parse(root / "checklist.yaml", ChecklistConfig),
        intents=_parse(INTENTS_FILE, IntentsConfig),
        report_keywords=_parse(REPORTS_FILE, ReportKeywords),
        edge=_parse(root / "edge.yaml", EdgeConfig),
        fleet=_parse(root / "fleet.yaml", FleetConfig),
        simulator=_parse(root / "simulator.yaml", SimulatorConfig),
    )
    _cross_check(cfg)
    return cfg


@lru_cache
def get_config() -> ShiftMateConfig:
    """Process-wide cached config (loaded once)."""
    return load_config()
