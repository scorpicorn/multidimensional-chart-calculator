"""Tests for Human Design base subdivision and Name lookup."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.human_design.bases import (
    HumanDesignBase,
    base_interval_width,
    calculate_base,
    load_base_names,
    longitude_offset_within_tone,
    lookup_human_design_base,
)
from src.human_design.gates import GateLineBoundary
from src.human_design.tones import tone_interval_width


MOTIVATION_BY_COLOR = {
    1: "Fear",
    2: "Hope",
    3: "Desire",
    4: "Need",
    5: "Guilt",
    6: "Innocence",
}
SENSE_BY_TONE = {
    1: "Security",
    2: "Uncertainty",
    3: "Action",
    4: "Meditation",
    5: "Judgement",
    6: "Acceptance",
}
NAME_BY_BASE = {
    1: "Movement",
    2: "Evolution",
    3: "Being",
    4: "Design",
    5: "Evolution",
}


def test_lookup_returns_base_1() -> None:
    boundaries = (simple_boundary(),)

    result = lookup_human_design_base(
        10.01,
        boundaries,
        MOTIVATION_BY_COLOR,
        SENSE_BY_TONE,
        NAME_BY_BASE,
    )

    assert result == HumanDesignBase(
        longitude_decimal=10.01,
        gate=1,
        line=1,
        color=1,
        motivation="Fear",
        tone=1,
        sense="Security",
        base=1,
        name="Movement",
    )


def test_lookup_returns_base_5() -> None:
    boundaries = (simple_boundary(),)

    result = lookup_human_design_base(
        10.16,
        boundaries,
        MOTIVATION_BY_COLOR,
        SENSE_BY_TONE,
        NAME_BY_BASE,
    )

    assert result.color == 1
    assert result.tone == 1
    assert result.base == 5
    assert result.name == "Evolution"


def test_exact_base_boundary_uses_next_half_open_base() -> None:
    boundary = simple_boundary()

    assert calculate_base(10.0 + (1.0 / 30.0), boundary) == 2


def test_wraparound_tone_base_subdivision() -> None:
    boundary = GateLineBoundary(
        gate=25,
        line=2,
        start_longitude=359.1875,
        end_longitude=0.125,
        wraparound=True,
    )

    assert tone_interval_width(boundary) == 0.026041666666666668
    assert base_interval_width(boundary) == 0.005208333333333334
    assert calculate_base(359.1875, boundary) == 1
    assert calculate_base(359.1875 + (0.15625 / 30.0), boundary) == 2
    assert longitude_offset_within_tone(0.124999, boundary) > 0.026
    assert calculate_base(0.124999, boundary) == 5


def test_load_base_names_from_ctb_ods() -> None:
    name_by_base = load_base_names(ROOT.parent / "CTB.ods")

    assert name_by_base[1] == "Movement"
    assert name_by_base[3] == "Being"
    assert name_by_base[5] == "Evolution"


def simple_boundary() -> GateLineBoundary:
    """Return a line interval with one-degree colors and 1/30-degree bases."""

    return GateLineBoundary(
        gate=1,
        line=1,
        start_longitude=10.0,
        end_longitude=16.0,
        wraparound=False,
    )
