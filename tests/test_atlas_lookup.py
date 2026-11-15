"""Tests for Atlas lookup."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.atlas_index import build_sqlite_database
from src.atlas_lookup import AtlasLookup
from src.atlas_parser import parse_atlas_file


def temp_file_path(suffix: str) -> Path:
    """Return a unique temp file path for a test case."""

    return Path(os.environ["TEMP"]) / f"atlas-lookup-{uuid.uuid4().hex}{suffix}"


def write_sample_atlas(path: Path) -> None:
    """Write a compact atlas fixture with duplicate city names."""

    path.write_text(
        "\n".join(
            [
                "@AC780  ; sample atlas",
                "; lookup fixture",
                "-YY 6",
                "-10.5\t40.1\tAA\tS\u00e3o Paulo\tAmerica/Sao_Paulo",
                "-11.5\t40.2\tAA\tSao-Paulo",
                "20.25\t10.5\tBB\tSpringfield\tEurope/Paris",
                "21.25\t11.5\tCC\tSpringfield",
                "22.25\t12.5\tCC\tSpringfield",
                "-73.9857\t40.7484\tUS\tNew York\tAmerica/New_York",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_lookup() -> AtlasLookup:
    atlas_path = temp_file_path(".as")
    db_path = temp_file_path(".sqlite3")
    write_sample_atlas(atlas_path)
    parsed = parse_atlas_file(atlas_path)
    build_sqlite_database(
        database_path=db_path,
        metadata=parsed.metadata,
        records=parsed.records,
    )
    return AtlasLookup(db_path)


def test_duplicate_city_names() -> None:
    lookup = build_lookup()

    results = lookup.lookup_exact("springfield")

    assert len(results) == 3
    assert [record.region_code for record in results] == ["BB", "CC", "CC"]


def test_lookup_exact_accent_insensitive() -> None:
    lookup = build_lookup()

    results = lookup.lookup_exact("sao paulo")

    assert len(results) == 2
    assert [record.city for record in results] == ["São Paulo", "Sao-Paulo"]
    assert all(record.city_norm == "sao paulo" for record in results)


def test_lookup_exact_city_region_first() -> None:
    lookup = build_lookup()

    results = lookup.lookup_exact("springfield", "CC")

    assert len(results) == 3
    assert [record.region_code for record in results] == ["CC", "CC", "BB"]
    assert all(record.city == "Springfield" for record in results)


def test_prefix_lookup() -> None:
    lookup = build_lookup()

    results = lookup.lookup_prefix("new")

    assert [record.city for record in results] == ["New York"]


def test_lookup_exact_region_code_is_case_insensitive() -> None:
    lookup = build_lookup()

    results = lookup.lookup_exact("springfield", "cc")

    assert [record.region_code for record in results] == ["CC", "CC", "BB"]


def test_lookup_prefix_respects_limit() -> None:
    lookup = build_lookup()

    results = lookup.lookup_prefix("s", limit=2)

    assert len(results) == 2
