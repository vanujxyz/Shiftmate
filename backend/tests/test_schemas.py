"""Milestone 2: the brief's sample rows parse into IntervalRecord; schemas behave as specified."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shiftmate.schema import EXPORTED_MODELS
from shiftmate.schema.enums import SeatbeltStatus, YesNo
from shiftmate.schema.intervals import BRIEF_COLUMNS, IntervalRecord, read_brief_csv, to_export_row
from shiftmate.schema.signals import SignalTick
from shiftmate.settings import REPO_ROOT

SAMPLE = REPO_ROOT / "fixtures" / "sample_rows.csv"


def test_sample_rows_parse_with_null_extensions() -> None:
    records = read_brief_csv(SAMPLE)
    assert len(records) == 4
    first = records[0]
    assert first.machine_id == "EXC001" and first.operator_id == "OP1001"
    assert first.engine_hours == 1523.5 and first.fuel_used_l == 5.2
    assert first.load_cycles == 12 and first.idling_time_min == 30
    assert first.seatbelt_status == SeatbeltStatus.FASTENED
    assert first.safety_alert_triggered == YesNo.NO
    assert first.timestamp.utcoffset() is not None  # naive sample time got the site timezone
    extension_fields = set(IntervalRecord.model_fields) - set(BRIEF_COLUMNS.values())
    for record in records:
        for name in extension_fields:
            assert getattr(record, name) is None, name


def test_sample_alert_rows_are_the_unfastened_ones() -> None:
    # D-003: in the sample, "Yes" coincides with an unfastened seatbelt.
    for record in read_brief_csv(SAMPLE):
        expected = YesNo.YES if record.seatbelt_status == SeatbeltStatus.UNFASTENED else YesNo.NO
        assert record.safety_alert_triggered == expected


def test_export_uses_brief_headers_first() -> None:
    row = to_export_row(read_brief_csv(SAMPLE)[1])
    assert list(row)[:9] == list(BRIEF_COLUMNS)
    assert row["Seatbelt Status"] == "Unfastened"
    assert "interval_start" in row


def test_interval_record_has_no_label_fields() -> None:
    # Golden rule 5: ground truth lives in a separate table, never on the record engines read.
    assert not [name for name in IntervalRecord.model_fields if name.startswith("label")]


def test_seatbelt_status_rejects_other_text() -> None:
    record = read_brief_csv(SAMPLE)[0].model_dump()
    record["seatbelt_status"] = "Maybe"
    with pytest.raises(ValidationError):
        IntervalRecord.model_validate(record)


def test_signal_tick_requires_timezone() -> None:
    base = dict(
        machine_id="EXC001",
        engine_on=True,
        engine_hours=1520.0,
        fuel_rate_lph=3.2,
        hydraulic_active=False,
        travel_speed_kmh=0.0,
        seatbelt_fastened=True,
        gps={"x_m": 1, "y_m": 2},
        heading_deg=0,
        ambient_temp_c=30,
        relative_humidity_pct=60,
        heat_index_c=33,
        precipitation_mm_h=0,
        wind_kmh=5,
        visibility_m=5000,
        is_night=False,
        ground_condition="dry",
    )
    tick = SignalTick(ts=datetime(2026, 9, 24, 7, 0, tzinfo=UTC), **base)
    assert tick.seat_occupied is None  # basic tier: not sensed
    with pytest.raises(ValidationError):
        SignalTick(ts=datetime(2026, 9, 24, 7, 0), **base)


def test_operator_model_has_no_personality() -> None:
    names = {m.__name__: m for m in EXPORTED_MODELS}
    assert "personality" not in names["Operator"].model_fields
