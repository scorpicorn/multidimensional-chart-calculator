"""Human Design gate and line lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree
from zipfile import ZipFile

REQUIRED_BOUNDARY_COLUMNS = (
    "Gate",
    "Line",
    "Start Longitude Decimal",
    "End Longitude Decimal",
    "Wraparound",
)

OFFICE_NAMESPACE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TABLE_NAMESPACE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT_NAMESPACE = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


class GateLineBoundaryError(ValueError):
    """Raised when gate line boundary data is invalid."""


class GateLineLookupError(LookupError):
    """Raised when a longitude does not map to exactly one gate line."""


@dataclass(frozen=True, slots=True)
class GateLine:
    """A Human Design gate.line placement."""

    gate: int
    line: int


@dataclass(frozen=True, slots=True)
class GateLineBoundary:
    """A spreadsheet-defined gate.line longitude interval."""

    gate: int
    line: int
    start_longitude: float
    end_longitude: float
    wraparound: bool


def normalize_longitude(value: float) -> float:
    """Normalize a longitude into the 0-360 degree range."""

    return value % 360.0


def longitude_in_boundary(longitude: float, boundary: GateLineBoundary) -> bool:
    """Return whether longitude is inside a half-open gate.line boundary."""

    normalized_longitude = normalize_longitude(longitude)
    start = normalize_longitude(boundary.start_longitude)
    end = normalize_longitude(boundary.end_longitude)
    if boundary.wraparound:
        return normalized_longitude >= start or normalized_longitude < end
    return start <= normalized_longitude < end


def lookup_gate_line_boundary(
    longitude: float,
    boundaries: Iterable[GateLineBoundary],
) -> GateLineBoundary:
    """Resolve a decimal longitude to its spreadsheet-defined gate.line boundary."""

    matches = [
        boundary
        for boundary in boundaries
        if longitude_in_boundary(longitude, boundary)
    ]
    if len(matches) != 1:
        raise GateLineLookupError(
            f"Expected one gate.line match for longitude {longitude}, found {len(matches)}."
        )
    return matches[0]


def lookup_gate_line(
    longitude: float,
    boundaries: Iterable[GateLineBoundary],
) -> GateLine:
    """Resolve a decimal longitude to its spreadsheet-defined gate.line."""

    match = lookup_gate_line_boundary(longitude, boundaries)
    return GateLine(gate=match.gate, line=match.line)


def load_gate_line_boundaries(path: str | Path) -> tuple[GateLineBoundary, ...]:
    """Load gate.line boundaries from an ODS spreadsheet."""

    spreadsheet_path = Path(path)
    if spreadsheet_path.suffix.lower() != ".ods":
        raise GateLineBoundaryError("Gate line boundary data must be an .ods spreadsheet.")

    rows = list(iter_ods_rows(spreadsheet_path))
    if not rows:
        raise GateLineBoundaryError("Gate line boundary spreadsheet is empty.")

    header = [str(value).strip() for value in rows[0]]
    missing_columns = [
        column for column in REQUIRED_BOUNDARY_COLUMNS if column not in header
    ]
    if missing_columns:
        raise GateLineBoundaryError(
            "Gate line boundary spreadsheet is missing columns: "
            + ", ".join(missing_columns)
        )

    column_indexes = {
        column: header.index(column)
        for column in REQUIRED_BOUNDARY_COLUMNS
    }
    boundaries: list[GateLineBoundary] = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(value != "" for value in row):
            continue
        try:
            boundaries.append(
                GateLineBoundary(
                    gate=parse_int_cell(row, column_indexes["Gate"]),
                    line=parse_int_cell(row, column_indexes["Line"]),
                    start_longitude=parse_float_cell(
                        row, column_indexes["Start Longitude Decimal"]
                    ),
                    end_longitude=parse_float_cell(
                        row, column_indexes["End Longitude Decimal"]
                    ),
                    wraparound=parse_bool_cell(row, column_indexes["Wraparound"]),
                )
            )
        except (IndexError, TypeError, ValueError) as exc:
            raise GateLineBoundaryError(
                f"Invalid gate line boundary data at row {row_number}."
            ) from exc

    if not boundaries:
        raise GateLineBoundaryError("Gate line boundary spreadsheet has no data rows.")
    return tuple(boundaries)


def parse_int_cell(row: list[object], index: int) -> int:
    """Parse an integer spreadsheet cell."""

    value = row[index]
    return int(float(str(value)))


def parse_float_cell(row: list[object], index: int) -> float:
    """Parse a float spreadsheet cell."""

    return float(str(row[index]))


def parse_bool_cell(row: list[object], index: int) -> bool:
    """Parse a boolean spreadsheet cell."""

    value = row[index]
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise GateLineBoundaryError(f"Invalid boolean value: {value!r}")


def iter_ods_rows(path: Path, sheet_name: str | None = None) -> Iterable[list[object]]:
    """Yield visible cell values from an ODS spreadsheet table."""

    with ZipFile(path) as archive:
        with archive.open("content.xml") as content_xml:
            root = ElementTree.parse(content_xml).getroot()

    if sheet_name is None:
        table = root.find(f".//{{{TABLE_NAMESPACE}}}table")
    else:
        table = None
        for candidate in root.findall(f".//{{{TABLE_NAMESPACE}}}table"):
            if candidate.get(f"{{{TABLE_NAMESPACE}}}name") == sheet_name:
                table = candidate
                break

    if table is None:
        if sheet_name is None:
            raise GateLineBoundaryError("Gate line boundary spreadsheet has no table.")
        raise GateLineBoundaryError(
            f"Gate line boundary spreadsheet has no sheet named {sheet_name!r}."
        )

    for row in table.findall(f"{{{TABLE_NAMESPACE}}}table-row"):
        row_repeat = int(row.get(f"{{{TABLE_NAMESPACE}}}number-rows-repeated", "1"))
        cells = expand_ods_row(row)
        for _ in range(row_repeat):
            yield cells


def expand_ods_row(row: ElementTree.Element) -> list[object]:
    """Return one ODS row with repeated cells expanded."""

    values: list[object] = []
    for cell in row.findall(f"{{{TABLE_NAMESPACE}}}table-cell"):
        cell_repeat = int(cell.get(f"{{{TABLE_NAMESPACE}}}number-columns-repeated", "1"))
        value = ods_cell_value(cell)
        values.extend([value] * cell_repeat)
    return values


def ods_cell_value(cell: ElementTree.Element) -> object:
    """Extract a typed value from one ODS cell."""

    value_type = cell.get(f"{{{OFFICE_NAMESPACE}}}value-type")
    if value_type == "float":
        return cell.get(f"{{{OFFICE_NAMESPACE}}}value", "")
    if value_type == "boolean":
        return cell.get(f"{{{OFFICE_NAMESPACE}}}boolean-value", "").lower() == "true"

    text_parts: list[str] = []
    for paragraph in cell.findall(f".//{{{TEXT_NAMESPACE}}}p"):
        text = "".join(paragraph.itertext())
        if text:
            text_parts.append(text)
    return "\n".join(text_parts)
