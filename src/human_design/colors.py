"""Human Design color subdivision and meaning lookup."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping

from .gates import (
    GateLineBoundary,
    GateLineBoundaryError,
    iter_ods_rows,
    lookup_gate_line_boundary,
    normalize_longitude,
    parse_int_cell,
)

COLOR_COUNT = 6
COLOR_TABLE_SHEET = "Color Table"
REQUIRED_COLOR_COLUMNS = ("Color", "Motivation")


class ColorMeaningError(ValueError):
    """Raised when color meaning data is invalid."""


@dataclass(frozen=True, slots=True)
class HumanDesignColor:
    """A Human Design gate.line.color placement with Motivation meaning."""

    longitude_decimal: float
    gate: int
    line: int
    color: int
    motivation: str


def line_interval_length(boundary: GateLineBoundary) -> float:
    """Return a line interval length while preserving zodiac wraparound."""

    start = normalize_longitude(boundary.start_longitude)
    end = normalize_longitude(boundary.end_longitude)
    if boundary.wraparound:
        return (end + 360.0) - start
    return end - start


def longitude_offset_within_line(longitude: float, boundary: GateLineBoundary) -> float:
    """Return longitude's decimal offset from the start of a line interval."""

    normalized_longitude = normalize_longitude(longitude)
    start = normalize_longitude(boundary.start_longitude)
    if boundary.wraparound and normalized_longitude < start:
        normalized_longitude += 360.0
    return normalized_longitude - start


def calculate_color(longitude: float, boundary: GateLineBoundary) -> int:
    """Calculate color by dividing a gate.line interval into six equal parts."""

    interval_length = line_interval_length(boundary)
    color_width = interval_length / COLOR_COUNT
    offset = longitude_offset_within_line(longitude, boundary)
    return subdivision_number(offset, color_width, COLOR_COUNT)


def subdivision_number(offset: float, width: float, count: int) -> int:
    """Return a 1-based half-open subdivision number."""

    position = offset / width
    nearest_boundary = round(position)
    if math.isclose(position, nearest_boundary, rel_tol=0.0, abs_tol=1e-10):
        position = float(nearest_boundary)
    return min(int(position) + 1, count)


def lookup_human_design_color(
    longitude: float,
    boundaries: tuple[GateLineBoundary, ...],
    motivation_by_color: Mapping[int, str],
) -> HumanDesignColor:
    """Resolve raw longitude to gate, line, color, and Motivation."""

    boundary = lookup_gate_line_boundary(longitude, boundaries)
    color = calculate_color(longitude, boundary)
    try:
        motivation = motivation_by_color[color]
    except KeyError as exc:
        raise ColorMeaningError(f"No Motivation found for color {color}.") from exc

    return HumanDesignColor(
        longitude_decimal=normalize_longitude(longitude),
        gate=boundary.gate,
        line=boundary.line,
        color=color,
        motivation=motivation,
    )


def load_color_motivations(path: str | Path) -> dict[int, str]:
    """Load Color -> Motivation meanings from CTB.ods."""

    spreadsheet_path = Path(path)
    if spreadsheet_path.suffix.lower() != ".ods":
        raise ColorMeaningError("Color meaning data must be an .ods spreadsheet.")

    try:
        rows = list(iter_ods_rows(spreadsheet_path, sheet_name=COLOR_TABLE_SHEET))
    except GateLineBoundaryError as exc:
        raise ColorMeaningError(str(exc)) from exc

    if not rows:
        raise ColorMeaningError("Color meaning spreadsheet is empty.")

    header = [str(value).strip() for value in rows[0]]
    missing_columns = [
        column for column in REQUIRED_COLOR_COLUMNS if column not in header
    ]
    if missing_columns:
        raise ColorMeaningError(
            "Color meaning spreadsheet is missing columns: "
            + ", ".join(missing_columns)
        )

    color_index = header.index("Color")
    motivation_index = header.index("Motivation")
    motivation_by_color: dict[int, str] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(value != "" for value in row):
            continue
        try:
            color = parse_int_cell(row, color_index)
            motivation = str(row[motivation_index]).strip()
        except (IndexError, TypeError, ValueError) as exc:
            raise ColorMeaningError(
                f"Invalid color meaning data at row {row_number}."
            ) from exc
        if not motivation:
            raise ColorMeaningError(f"Missing Motivation at row {row_number}.")
        motivation_by_color[color] = motivation

    expected_colors = set(range(1, COLOR_COUNT + 1))
    missing_colors = expected_colors.difference(motivation_by_color)
    if missing_colors:
        missing_text = ", ".join(str(color) for color in sorted(missing_colors))
        raise ColorMeaningError(f"Missing Motivation rows for colors: {missing_text}.")
    return motivation_by_color
