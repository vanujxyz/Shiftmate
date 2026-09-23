"""Milestone 2: every config file loads; bad config fails fast; cross-references hold."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from shiftmate.config_loader import REQUIRED_LESSONS, ConfigError, get_config, load_config
from shiftmate.schema.enums import GroundCondition, MachineType, SensorTier
from shiftmate.settings import REPO_ROOT

LOCALES = REPO_ROOT / "frontend" / "packages" / "i18n" / "src" / "locales"


@pytest.fixture(scope="module")
def cfg():
    return get_config()


def _flatten(tree: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, path))
        else:
            out[path] = value
    return out


def test_all_configs_load(cfg) -> None:
    assert set(cfg.profiles) == set(MachineType)
    assert set(cfg.sites) == {"CHN-HWY-01", "PNQ-MET-01", "PIL-MIN-01", "TRO-RD-01"}
    assert len(cfg.lessons.lessons) == 12
    assert {lesson.id for lesson in cfg.lessons.lessons} == REQUIRED_LESSONS
    assert len(cfg.checklist.items) == 7


def test_trd_defaults_kept(cfg) -> None:
    exc = cfg.profiles[MachineType.EXCAVATOR]
    assert (exc.proximity_m.caution, exc.proximity_m.danger, exc.proximity_m.critical) == (
        10.0,
        6.0,
        3.5,
    )
    assert exc.fuel_lph.idle == 3.2
    assert cfg.risk_model.bands["amber"] == (40, 69)
    assert cfg.alert_policy.paused_definition.idle_seconds == 30
    assert cfg.privacy.supervisor_aggregates_min_group_size == 3
    seatbelt = cfg.safety_rules.rule("SEATBELT_MOVING")
    assert seatbelt.priority == "P1" and seatbelt.sustain_s == 2


def test_fleet_composition_matches_trd(cfg) -> None:
    # TRD §7.1: 60 machines (30/18/12), sites 24/14/14/8, 80 operators
    totals = {t: sum(s.fleet.count(t) for s in cfg.sites.values()) for t in MachineType}
    assert totals == {
        MachineType.EXCAVATOR: 30,
        MachineType.WHEEL_LOADER: 18,
        MachineType.DOZER: 12,
    }
    per_site = {sid: sum(s.fleet.count(t) for t in MachineType) for sid, s in cfg.sites.items()}
    assert per_site == {"CHN-HWY-01": 24, "PNQ-MET-01": 14, "PIL-MIN-01": 14, "TRO-RD-01": 8}
    assert sum(s.operators for s in cfg.sites.values()) == 80
    assert cfg.sites["CHN-HWY-01"].operator_names[0] == "Ravi Kumar"


def test_sensor_tier_inheritance(cfg) -> None:
    basic = cfg.sensor_tiers.signals_for(SensorTier.BASIC)
    advanced = cfg.sensor_tiers.signals_for(SensorTier.ADVANCED)
    assert "seat_occupied" not in basic
    assert basic < advanced
    assert {"proximity_m", "truck_in_loading_zone", "seat_occupied"} <= advanced
    assert not cfg.sensor_tiers.feature_enabled("unattended_running", SensorTier.BASIC)


def test_every_message_key_is_translated(cfg) -> None:
    for lang in ("en", "hi", "ta"):
        flat = _flatten(json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8")))
        for rule in cfg.safety_rules.rules:
            for part in ("title", "action", "speak"):
                assert f"{rule.message_key}.{part}" in flat, (lang, rule.id, part)
        for feature in cfg.anomaly.features:
            assert feature.message_key in flat, (lang, feature.code)
        for keys in cfg.estimation.reason_keys.values():
            for key in keys.expanded([g.value for g in GroundCondition]):
                assert key in flat, (lang, key)
        for reason in cfg.idle_rules.order:
            assert f"idle.{reason}" in flat, (lang, reason)


def test_lessons_and_checklist_have_three_languages(cfg) -> None:
    # LocalizedText requires non-empty en/hi/ta; also check hi/ta are not copies of English.
    def texts(model):
        if hasattr(model, "en") and hasattr(model, "ta"):
            yield model
        elif hasattr(model, "__iter__") and not isinstance(model, str | bytes):
            for item in model:
                yield from texts(item)
        elif hasattr(model, "model_fields"):
            for name in type(model).model_fields:
                yield from texts(getattr(model, name))

    all_texts = list(texts(cfg.lessons.lessons)) + list(texts(cfg.checklist.items))
    assert len(all_texts) > 100
    for text in all_texts:
        assert text.hi != text.en and text.ta != text.en, text.en


def _copy_config(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(REPO_ROOT / "config", target)
    return target


def test_unknown_key_fails_fast(tmp_path) -> None:
    root = _copy_config(tmp_path)
    path = root / "risk_model.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["surprise"] = 1
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="risk_model.yaml"):
        load_config(root)


def test_bad_proximity_order_fails(tmp_path) -> None:
    root = _copy_config(tmp_path)
    path = root / "machine_profiles" / "dozer.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["proximity_m"] = {"caution": 3, "danger": 7, "critical": 4}
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="caution > danger > critical"):
        load_config(root)


def test_unknown_lesson_trigger_fails(tmp_path) -> None:
    root = _copy_config(tmp_path)
    path = root / "lessons.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "triggers: [NIGHT]", "triggers: [NIGHT, NOT_A_THING]"
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="NOT_A_THING"):
        load_config(root)


def test_rule_with_unknown_signal_fails(tmp_path) -> None:
    root = _copy_config(tmp_path)
    path = root / "safety_rules.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "requires_signals: [seat_occupied]", "requires_signals: [mind_reader]"
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="mind_reader"):
        load_config(root)
