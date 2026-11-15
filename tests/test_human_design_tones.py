"""Tests for Human Design tone subdivision and Sense lookup."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.human_design.gates import GateLineBoundary
from src.human_design.tones import (
    HumanDesignTone,
    calculate_tone,
    color_interval_width,
    load_tone_senses,
    longitude_offset_within_color,
    lookup_human_design_tone,
    tone_interval_width,
)


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


def test_lookup_returns_tone_1() -> None:
    boundaries = (simple_boundary(),)

    result = lookup_human_design_tone(
        10.05,
        boundaries,
        MOTIVATION_BY_COLOR,
        SENSE_BY_TONE,
    )

    assert result == HumanDesignTone(
        longitude_decimal=10.05,
        gate=1,
        line=1,
        color=1,
        motivation="Fear",
        tone=1,
        sense="Security",
    )


def test_lookup_returns_tone_6() -> None:
    boundaries = (simple_boundary(),)

    result = lookup_human_design_tone(
        10.9,
        boundaries,
        MOTIVATION_BY_COLOR,
        SENSE_BY_TONE,
    )

    assert result.color == 1
    assert result.tone == 6
    assert result.sense == "Acceptance"


def test_exact_tone_boundary_uses_next_half_open_tone() -> None:
    boundary = simple_boundary()

    assert calculate_tone(10.0 + (1.0 / 6.0), boundary) == 2


def test_wraparound_tone_subdivision() -> None:
    boundary = GateLineBoundary(
        gate=25,
        line=2,
        start_longitude=359.1875,
        end_longitude=0.125,
        wraparound=True,
    )

    assert color_interval_width(boundary) == 0.15625
    assert tone_interval_width(boundary) == 0.026041666666666668
    assert calculate_tone(359.1875, boundary) == 1
    assert calculate_tone(359.1875 + (0.15625 / 6.0), boundary) == 2
    assert longitude_offset_within_color(0.0, boundary) == 0.03125
    assert calculate_tone(0.0, boundary) == 2
    assert calculate_tone(0.124999, boundary) == 6


def test_load_tone_senses_from_ctb_ods() -> None:
    sense_by_tone = load_tone_senses(ROOT.parent / "CTB.ods")

    assert sense_by_tone[1] == "Security"
    assert sense_by_tone[4] == "Meditation"
    assert sense_by_tone[6] == "Acceptance"


def simple_boundary() -> GateLineBoundary:
    """Return a line interval with one-degree colors and one-sixth-degree tones."""

    return GateLineBoundary(
        gate=1,
        line=1,
        start_longitude=10.0,
        end_longitude=16.0,
        wraparound=False,
    )
