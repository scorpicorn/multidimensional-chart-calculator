"""Tests for Human Design gate.line boundary lookup."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.human_design.gates import (
    GateLine,
    GateLineBoundary,
    GateLineBoundaryError,
    lookup_gate_line,
    load_gate_line_boundaries,
)


def test_lookup_uses_half_open_intervals() -> None:
    boundaries = (
        GateLineBoundary(
            gate=25,
            line=3,
            start_longitude=0.125,
            end_longitude=1.0625,
            wraparound=False,
        ),
        GateLineBoundary(
            gate=25,
            line=4,
            start_longitude=1.0625,
            end_longitude=2.0,
            wraparound=False,
        ),
    )

    assert lookup_gate_line(0.125, boundaries) == GateLine(gate=25, line=3)
    assert lookup_gate_line(1.062499, boundaries) == GateLine(gate=25, line=3)
    assert lookup_gate_line(1.0625, boundaries) == GateLine(gate=25, line=4)


def test_lookup_handles_wraparound_boundaries() -> None:
    boundaries = (
        GateLineBoundary(
            gate=24,
            line=6,
            start_longitude=359.5,
            end_longitude=0.125,
            wraparound=True,
        ),
        GateLineBoundary(
            gate=25,
            line=3,
            start_longitude=0.125,
            end_longitude=1.0625,
            wraparound=False,
        ),
    )

    assert lookup_gate_line(359.75, boundaries) == GateLine(gate=24, line=6)
    assert lookup_gate_line(0.0, boundaries) == GateLine(gate=24, line=6)
    assert lookup_gate_line(0.125, boundaries) == GateLine(gate=25, line=3)


def test_lookup_handles_true_25_2_wraparound_boundary() -> None:
    boundaries = (
        GateLineBoundary(
            gate=25,
            line=2,
            start_longitude=359.1875,
            end_longitude=0.125,
            wraparound=True,
        ),
        GateLineBoundary(
            gate=25,
            line=3,
            start_longitude=0.125,
            end_longitude=1.0625,
            wraparound=False,
        ),
    )

    assert lookup_gate_line(359.5, boundaries) == GateLine(gate=25, line=2)
    assert lookup_gate_line(0.0, boundaries) == GateLine(gate=25, line=2)
    assert lookup_gate_line(0.124999, boundaries) == GateLine(gate=25, line=2)
    assert lookup_gate_line(0.125, boundaries) == GateLine(gate=25, line=3)


def test_lookup_normalizes_longitudes() -> None:
    boundaries = (
        GateLineBoundary(
            gate=25,
            line=3,
            start_longitude=0.125,
            end_longitude=1.0625,
            wraparound=False,
        ),
    )

    assert lookup_gate_line(360.125, boundaries) == GateLine(gate=25, line=3)
    assert lookup_gate_line(-359.875, boundaries) == GateLine(gate=25, line=3)


def test_load_gate_line_boundaries_reads_confirmed_ods_columns() -> None:
    spreadsheet_path = temp_spreadsheet_path()
    write_minimal_ods(
        spreadsheet_path,
        [
            [
                "Gate",
                "Line",
                "Start Longitude Decimal",
                "End Longitude Decimal",
                "Wraparound",
            ],
            [25, 3, 0.125, 1.0625, False],
            [24, 6, 359.5, 0.125, True],
        ],
    )

    boundaries = load_gate_line_boundaries(spreadsheet_path)

    assert boundaries == (
        GateLineBoundary(
            gate=25,
            line=3,
            start_longitude=0.125,
            end_longitude=1.0625,
            wraparound=False,
        ),
        GateLineBoundary(
            gate=24,
            line=6,
            start_longitude=359.5,
            end_longitude=0.125,
            wraparound=True,
        ),
    )


def test_load_gate_line_boundaries_requires_confirmed_columns() -> None:
    spreadsheet_path = temp_spreadsheet_path()
    write_minimal_ods(spreadsheet_path, [["Gate", "Line"], [25, 3]])

    try:
        load_gate_line_boundaries(spreadsheet_path)
    except GateLineBoundaryError as exc:
        assert "Start Longitude Decimal" in str(exc)
    else:
        raise AssertionError("Expected missing spreadsheet columns to fail")


def temp_spreadsheet_path() -> Path:
    """Return a unique project-local ODS path for tests."""

    test_dir = ROOT / ".tmp" / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir / f"gate-line-{uuid.uuid4().hex}.ods"


def write_minimal_ods(path: Path, rows: list[list[object]]) -> None:
    """Write a compact ODS file containing only the cells needed by tests."""

    table_rows = "\n".join(write_ods_row(row) for row in rows)
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
  <office:body>
    <office:spreadsheet>
      <table:table table:name="Gate Line Boundaries">
        {table_rows}
      </table:table>
    </office:spreadsheet>
  </office:body>
</office:document-content>
"""
    with ZipFile(path, "w") as archive:
        archive.writestr("content.xml", content)


def write_ods_row(values: list[object]) -> str:
    """Serialize one tiny ODS row for tests."""

    cells = "".join(write_ods_cell(value) for value in values)
    return f"<table:table-row>{cells}</table:table-row>"


def write_ods_cell(value: object) -> str:
    """Serialize one tiny ODS cell for tests."""

    if isinstance(value, bool):
        text = "TRUE" if value else "FALSE"
        boolean_value = str(value).lower()
        return (
            '<table:table-cell office:value-type="boolean" '
            f'office:boolean-value="{boolean_value}"><text:p>{text}</text:p>'
            "</table:table-cell>"
        )
    if isinstance(value, (int, float)):
        return (
            '<table:table-cell office:value-type="float" '
            f'office:value="{value}"><text:p>{value}</text:p></table:table-cell>'
        )
    return (
        '<table:table-cell office:value-type="string">'
        f"<text:p>{value}</text:p></table:table-cell>"
    )
