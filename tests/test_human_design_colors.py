"""Tests for Human Design color subdivision and Motivation lookup."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.human_design.colors import (
    HumanDesignColor,
    calculate_color,
    line_interval_length,
    load_color_motivations,
    lookup_human_design_color,
    longitude_offset_within_line,
)
from src.human_design.gates import GateLineBoundary


MOTIVATION_BY_COLOR = {
    1: "Fear",
    2: "Hope",
    3: "Desire",
    4: "Need",
    5: "Guilt",
    6: "Innocence",
}


def test_lookup_returns_color_1() -> None:
    boundaries = (simple_boundary(),)

    result = lookup_human_design_color(
        10.5,
        boundaries,
        MOTIVATION_BY_COLOR,
    )

    assert result == HumanDesignColor(
        longitude_decimal=10.5,
        gate=1,
        line=1,
        color=1,
        motivation="Fear",
    )


def test_lookup_returns_color_6() -> None:
    boundaries = (simple_boundary(),)

    result = lookup_human_design_color(
        15.5,
        boundaries,
        MOTIVATION_BY_COLOR,
    )

    assert result.color == 6
    assert result.motivation == "Innocence"


def test_exact_color_boundary_uses_next_half_open_color() -> None:
    boundary = simple_boundary()

    assert calculate_color(11.0, boundary) == 2


def test_wraparound_line_color_subdivision() -> None:
    boundary = GateLineBoundary(
        gate=25,
        line=2,
        start_longitude=359.1875,
        end_longitude=0.125,
        wraparound=True,
    )

    assert line_interval_length(boundary) == 0.9375
    assert longitude_offset_within_line(0.0, boundary) == 0.8125
    assert calculate_color(359.1875, boundary) == 1
    assert calculate_color(359.34375, boundary) == 2
    assert calculate_color(0.0, boundary) == 6
    assert calculate_color(0.124999, boundary) == 6


def test_load_color_motivations_from_ctb_ods() -> None:
    motivation_by_color = load_color_motivations(ROOT.parent / "CTB.ods")

    assert motivation_by_color[1] == "Fear"
    assert motivation_by_color[2] == "Hope"
    assert motivation_by_color[6] == "Innocence"


def simple_boundary() -> GateLineBoundary:
    """Return a line interval that divides into one-degree colors."""

    return GateLineBoundary(
        gate=1,
        line=1,
        start_longitude=10.0,
        end_longitude=16.0,
        wraparound=False,
    )
