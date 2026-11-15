"""Human Design tone subdivision and meaning lookup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .colors import (
    COLOR_COUNT,
    ColorMeaningError,
    calculate_color,
    line_interval_length,
    load_color_motivations,
    longitude_offset_within_line,
    lookup_human_design_color,
    subdivision_number,
)
from .gates import (
    GateLineBoundary,
    GateLineBoundaryError,
    iter_ods_rows,
    lookup_gate_line_boundary,
    parse_int_cell,
)

TONE_COUNT = 6
TONE_TABLE_SHEET = "Tone Table"
REQUIRED_TONE_COLUMNS = ("Tone", "Sense")


class ToneMeaningError(ValueError):
    """Raised when tone meaning data is invalid."""


@dataclass(frozen=True, slots=True)
class HumanDesignTone:
    """A Human Design gate.line.color.tone placement with meanings."""

    longitude_decimal: float
    gate: int
    line: int
    color: int
    motivation: str
    tone: int
    sense: str


def color_interval_width(boundary: GateLineBoundary) -> float:
    """Return the decimal width of one color inside a line interval."""

    return line_interval_length(boundary) / COLOR_COUNT


def tone_interval_width(boundary: GateLineBoundary) -> float:
    """Return the decimal width of one tone inside a color interval."""

    return color_interval_width(boundary) / TONE_COUNT


def longitude_offset_within_color(longitude: float, boundary: GateLineBoundary) -> float:
    """Return longitude's decimal offset from the start of its color interval."""

    color = calculate_color(longitude, boundary)
    color_start_offset = (color - 1) * color_interval_width(boundary)
    return longitude_offset_within_line(longitude, boundary) - color_start_offset


def calculate_tone(longitude: float, boundary: GateLineBoundary) -> int:
    """Calculate tone by dividing the resolved color interval into six parts."""

    offset = longitude_offset_within_color(longitude, boundary)
    return subdivision_number(offset, tone_interval_width(boundary), TONE_COUNT)


def lookup_human_design_tone(
    longitude: float,
    boundaries: tuple[GateLineBoundary, ...],
    motivation_by_color: Mapping[int, str],
    sense_by_tone: Mapping[int, str],
) -> HumanDesignTone:
    """Resolve raw longitude to gate, line, color, Motivation, tone, and Sense."""

    color_result = lookup_human_design_color(
        longitude,
        boundaries,
        motivation_by_color,
    )
    boundary = lookup_gate_line_boundary(longitude, boundaries)
    tone = calculate_tone(longitude, boundary)
    try:
        sense = sense_by_tone[tone]
    except KeyError as exc:
        raise ToneMeaningError(f"No Sense found for tone {tone}.") from exc

    return HumanDesignTone(
        longitude_decimal=color_result.longitude_decimal,
        gate=color_result.gate,
        line=color_result.line,
        color=color_result.color,
        motivation=color_result.motivation,
        tone=tone,
        sense=sense,
    )


def lookup_human_design_tone_from_workbooks(
    longitude: float,
    boundaries: tuple[GateLineBoundary, ...],
    ctb_path: str | Path,
) -> HumanDesignTone:
    """Resolve raw longitude using CTB.ods color and tone meaning tables."""

    return lookup_human_design_tone(
        longitude,
        boundaries,
        load_color_motivations(ctb_path),
        load_tone_senses(ctb_path),
    )


def load_tone_senses(path: str | Path) -> dict[int, str]:
    """Load Tone -> Sense meanings from CTB.ods."""

    spreadsheet_path = Path(path)
    if spreadsheet_path.suffix.lower() != ".ods":
        raise ToneMeaningError("Tone meaning data must be an .ods spreadsheet.")

    try:
        rows = list(iter_ods_rows(spreadsheet_path, sheet_name=TONE_TABLE_SHEET))
    except GateLineBoundaryError as exc:
        raise ToneMeaningError(str(exc)) from exc
    except ColorMeaningError as exc:
        raise ToneMeaningError(str(exc)) from exc

    if not rows:
        raise ToneMeaningError("Tone meaning spreadsheet is empty.")

    header = [str(value).strip() for value in rows[0]]
    missing_columns = [
        column for column in REQUIRED_TONE_COLUMNS if column not in header
    ]
    if missing_columns:
        raise ToneMeaningError(
            "Tone meaning spreadsheet is missing columns: "
            + ", ".join(missing_columns)
        )

    tone_index = header.index("Tone")
    sense_index = header.index("Sense")
    sense_by_tone: dict[int, str] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(value != "" for value in row):
            continue
        try:
            tone = parse_int_cell(row, tone_index)
            sense = str(row[sense_index]).strip()
        except (IndexError, TypeError, ValueError) as exc:
            raise ToneMeaningError(
                f"Invalid tone meaning data at row {row_number}."
            ) from exc
        if not sense:
            raise ToneMeaningError(f"Missing Sense at row {row_number}.")
        sense_by_tone[tone] = sense

    expected_tones = set(range(1, TONE_COUNT + 1))
    missing_tones = expected_tones.difference(sense_by_tone)
    if missing_tones:
        missing_text = ", ".join(str(tone) for tone in sorted(missing_tones))
        raise ToneMeaningError(f"Missing Sense rows for tones: {missing_text}.")
    return sense_by_tone
