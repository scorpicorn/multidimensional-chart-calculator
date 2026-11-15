"""Human Design base subdivision and meaning lookup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .colors import (
    ColorMeaningError,
    load_color_motivations,
    subdivision_number,
)
from .gates import (
    GateLineBoundary,
    GateLineBoundaryError,
    iter_ods_rows,
    lookup_gate_line_boundary,
    parse_int_cell,
)
from .tones import (
    TONE_COUNT,
    ToneMeaningError,
    load_tone_senses,
    longitude_offset_within_color,
    lookup_human_design_tone,
    tone_interval_width,
)

BASE_COUNT = 5
BASE_TABLE_SHEET = "Base Table"
REQUIRED_BASE_COLUMNS = ("Base", "Name")


class BaseMeaningError(ValueError):
    """Raised when base meaning data is invalid."""


@dataclass(frozen=True, slots=True)
class HumanDesignBase:
    """A Human Design gate.line.color.tone.base placement with meanings."""

    longitude_decimal: float
    gate: int
    line: int
    color: int
    motivation: str
    tone: int
    sense: str
    base: int
    name: str


def base_interval_width(boundary: GateLineBoundary) -> float:
    """Return the decimal width of one base inside a tone interval."""

    return tone_interval_width(boundary) / BASE_COUNT


def longitude_offset_within_tone(longitude: float, boundary: GateLineBoundary) -> float:
    """Return longitude's decimal offset from the start of its tone interval."""

    tone = subdivision_number(
        longitude_offset_within_color(longitude, boundary),
        tone_interval_width(boundary),
        TONE_COUNT,
    )
    tone_start_offset = (tone - 1) * tone_interval_width(boundary)
    return longitude_offset_within_color(longitude, boundary) - tone_start_offset


def calculate_base(longitude: float, boundary: GateLineBoundary) -> int:
    """Calculate base by dividing the resolved tone interval into five parts."""

    offset = longitude_offset_within_tone(longitude, boundary)
    return subdivision_number(offset, base_interval_width(boundary), BASE_COUNT)


def lookup_human_design_base(
    longitude: float,
    boundaries: tuple[GateLineBoundary, ...],
    motivation_by_color: Mapping[int, str],
    sense_by_tone: Mapping[int, str],
    name_by_base: Mapping[int, str],
) -> HumanDesignBase:
    """Resolve raw longitude to gate, line, color, tone, base, and meanings."""

    tone_result = lookup_human_design_tone(
        longitude,
        boundaries,
        motivation_by_color,
        sense_by_tone,
    )
    boundary = lookup_gate_line_boundary(longitude, boundaries)
    base = calculate_base(longitude, boundary)
    try:
        name = name_by_base[base]
    except KeyError as exc:
        raise BaseMeaningError(f"No Name found for base {base}.") from exc

    return HumanDesignBase(
        longitude_decimal=tone_result.longitude_decimal,
        gate=tone_result.gate,
        line=tone_result.line,
        color=tone_result.color,
        motivation=tone_result.motivation,
        tone=tone_result.tone,
        sense=tone_result.sense,
        base=base,
        name=name,
    )


def lookup_human_design_base_from_workbooks(
    longitude: float,
    boundaries: tuple[GateLineBoundary, ...],
    ctb_path: str | Path,
) -> HumanDesignBase:
    """Resolve raw longitude using CTB.ods color, tone, and base tables."""

    return lookup_human_design_base(
        longitude,
        boundaries,
        load_color_motivations(ctb_path),
        load_tone_senses(ctb_path),
        load_base_names(ctb_path),
    )


def load_base_names(path: str | Path) -> dict[int, str]:
    """Load Base -> Name meanings from CTB.ods."""

    spreadsheet_path = Path(path)
    if spreadsheet_path.suffix.lower() != ".ods":
        raise BaseMeaningError("Base meaning data must be an .ods spreadsheet.")

    try:
        rows = list(iter_ods_rows(spreadsheet_path, sheet_name=BASE_TABLE_SHEET))
    except (GateLineBoundaryError, ColorMeaningError, ToneMeaningError) as exc:
        raise BaseMeaningError(str(exc)) from exc

    if not rows:
        raise BaseMeaningError("Base meaning spreadsheet is empty.")

    header = [str(value).strip() for value in rows[0]]
    missing_columns = [
        column for column in REQUIRED_BASE_COLUMNS if column not in header
    ]
    if missing_columns:
        raise BaseMeaningError(
            "Base meaning spreadsheet is missing columns: "
            + ", ".join(missing_columns)
        )

    base_index = header.index("Base")
    name_index = header.index("Name")
    name_by_base: dict[int, str] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(value != "" for value in row):
            continue
        try:
            base = parse_int_cell(row, base_index)
            name = str(row[name_index]).strip()
        except (IndexError, TypeError, ValueError) as exc:
            raise BaseMeaningError(
                f"Invalid base meaning data at row {row_number}."
            ) from exc
        if not name:
            raise BaseMeaningError(f"Missing Name at row {row_number}.")
        name_by_base[base] = name

    expected_bases = set(range(1, BASE_COUNT + 1))
    missing_bases = expected_bases.difference(name_by_base)
    if missing_bases:
        missing_text = ", ".join(str(base) for base in sorted(missing_bases))
        raise BaseMeaningError(f"Missing Name rows for bases: {missing_text}.")
    return name_by_base
