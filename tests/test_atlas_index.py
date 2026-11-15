"""Tests for Atlas compiled index building."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.atlas_index import (
    MAX_PREFIX_LENGTH,
    build_sqlite_database,
    load_compiled_atlas,
    lookup_record_ids_by_city,
    lookup_record_ids_by_city_region,
    lookup_record_ids_by_prefix,
    normalize_region_code,
)
from src.atlas_parser import normalize_city_name, parse_atlas_file


def temp_file_path(suffix: str) -> Path:
    """Return a unique temp file path for a test case."""

    return Path(os.environ["TEMP"]) / f"atlas-index-{uuid.uuid4().hex}{suffix}"


def write_sample_atlas(path: Path) -> None:
    """Write a compact atlas fixture for index tests."""

    path.write_text(
        "\n".join(
            [
                "@AC780  ; sample atlas",
                "-YY 5",
                "-10.5\t40.1\tAA\tS\u00e3o Paulo\tAmerica/Sao_Paulo",
                "-11.5\t40.2\tAA\tSao-Paulo",
                "20.25\t10.5\tBB\tSpringfield\tEurope/Paris",
                "21.25\t11.5\tCC\tSpringfield",
                "-73.9857\t40.7484\tUS\tNew York City\tAmerica/New_York",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_compiled_atlas():
    """Build and load a compiled atlas artifact for testing."""

    atlas_path = temp_file_path(".as")
    db_path = temp_file_path(".sqlite3")
    write_sample_atlas(atlas_path)
    parsed = parse_atlas_file(atlas_path)
    build_sqlite_database(
        database_path=db_path,
        metadata=parsed.metadata,
        records=parsed.records,
    )
    return load_compiled_atlas(db_path)


def test_exact_city_indexing() -> None:
    compiled = build_compiled_atlas()

    record_ids = lookup_record_ids_by_city(compiled, normalize_city_name("sao paulo"))

    assert record_ids == [1, 2]


def test_city_region_indexing() -> None:
    compiled = build_compiled_atlas()

    record_ids = lookup_record_ids_by_city_region(
        compiled,
        normalize_city_name("springfield"),
        normalize_region_code("CC"),
    )

    assert record_ids == [4]


def test_prefix_indexing() -> None:
    compiled = build_compiled_atlas()

    record_ids = lookup_record_ids_by_prefix(
        compiled,
        normalize_city_name("new york city")[:MAX_PREFIX_LENGTH],
    )

    assert record_ids == [5]


def test_duplicate_city_names_return_multiple_candidates() -> None:
    compiled = build_compiled_atlas()

    record_ids = lookup_record_ids_by_city(compiled, normalize_city_name("springfield"))

    assert record_ids == [3, 4]


def test_prefix_indexing_caps_prefix_length() -> None:
    compiled = build_compiled_atlas()

    record_ids = lookup_record_ids_by_prefix(
        compiled,
        normalize_city_name("new york city extra words"),
    )

    assert record_ids == [5]
