"""Tests for Atlas parsing."""

from __future__ import annotations

import math
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.atlas_parser import (
    AtlasParseError,
    astrolog_to_standard_longitude,
    normalize_city_name,
    parse_atlas_file,
)


def temp_file_path(suffix: str) -> Path:
    """Return a unique temp file path for a test case."""

    return Path(os.environ["TEMP"]) / f"atlas-parser-{uuid.uuid4().hex}{suffix}"


def write_sample_atlas(path: Path) -> None:
    """Write a compact atlas fixture with inheritance and duplicate names."""

    path.write_text(
        "\n".join(
            [
                "@AC780  ; sample atlas",
                "; comment one",
                "; comment two",
                "-YY 5",
                "-10.5\t40.1\tAA\tS\u00e3o Paulo\tAmerica/Sao_Paulo",
                "-11.5\t40.2\tAA\tSao-Paulo",
                "20.25\t10.5\tBB\tSpringfield\tEurope/Paris",
                "21.25\t11.5\tCC\tSpringfield",
                "22.25\t12.5\tCC\tSpringfield",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_timezone_inheritance() -> None:
    atlas_path = temp_file_path(".as")
    write_sample_atlas(atlas_path)

    parsed = parse_atlas_file(atlas_path)

    assert parsed.metadata.source_tag == "@AC780"
    assert parsed.metadata.declared_record_count == 5
    assert parsed.metadata.comment_lines == ("comment one", "comment two")
    assert parsed.records[1].timezone == "America/Sao_Paulo"
    assert parsed.records[3].timezone == "Europe/Paris"


def test_longitude_normalization() -> None:
    assert math.isclose(astrolog_to_standard_longitude(-54.397), 54.397)
    assert math.isclose(astrolog_to_standard_longitude(61.8433), -61.8433)


def test_comment_and_metadata_lines_are_skipped() -> None:
    atlas_path = temp_file_path(".as")
    atlas_path.write_text(
        "\n".join(
            [
                "@AC780  ; sample atlas",
                "; comment one",
                "",
                "-YY 2",
                "-10.5\t40.1\tAA\tS\u00e3o Paulo\tAmerica/Sao_Paulo",
                "; comment two",
                "-11.5\t40.2\tAA\tSao-Paulo",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    parsed = parse_atlas_file(atlas_path)

    assert len(parsed.records) == 2
    assert parsed.records[0].city == "S\u00e3o Paulo"
    assert parsed.records[1].timezone == "America/Sao_Paulo"


def test_malformed_rows_raise_predictable_error() -> None:
    atlas_path = temp_file_path(".as")
    atlas_path.write_text(
        "\n".join(
            [
                "@AC780  ; sample atlas",
                "-YY 1",
                "-10.5\t40.1\tAA",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        parse_atlas_file(atlas_path)
    except AtlasParseError as exc:
        assert "Unexpected field count" in str(exc)
    else:
        raise AssertionError("Expected AtlasParseError for malformed input")


def test_missing_initial_timezone_raises_predictable_error() -> None:
    atlas_path = temp_file_path(".as")
    atlas_path.write_text(
        "\n".join(
            [
                "@AC780  ; sample atlas",
                "-YY 1",
                "-10.5\t40.1\tAA\tSpringfield",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        parse_atlas_file(atlas_path)
    except AtlasParseError as exc:
        assert "Missing timezone" in str(exc)
    else:
        raise AssertionError("Expected AtlasParseError for missing inherited timezone")


def test_city_normalization_collapses_punctuation_and_diacritics() -> None:
    assert normalize_city_name("  São-Paulo!!!  ") == "sao paulo"
    assert normalize_city_name("St.   John's") == "st john s"
