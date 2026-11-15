"""Tests for the FastAPI application layer."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.atlas_index import build_sqlite_database
from src.atlas_parser import parse_atlas_file
from src.atlas_lookup import AtlasLookup
from src.main import BirthtimeNormalizationRequest, normalize_birthtime


def temp_file_path(suffix: str) -> Path:
    """Return a unique temp file path for a test case."""

    return Path(os.environ["TEMP"]) / f"atlas-main-{uuid.uuid4().hex}{suffix}"


def write_sample_atlas(path: Path) -> None:
    """Write a compact atlas fixture for API tests."""

    path.write_text(
        "\n".join(
            [
                "@AC780  ; sample atlas",
                "-YY 5",
                "-73.9857\t40.7484\tUS\tNew York City\tAmerica/New_York",
                "-0.1276\t51.5072\tGB\tLondon\tEurope/London",
                "20.25\t10.5\tBB\tSpringfield\tEurope/Paris",
                "21.25\t11.5\tCC\tSpringfield",
                "22.25\t12.5\tCC\tSpringfield",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_test_database() -> Path:
    """Build a compiled atlas database for API tests."""

    atlas_path = temp_file_path(".as")
    db_path = temp_file_path(".sqlite3")
    write_sample_atlas(atlas_path)
    parsed = parse_atlas_file(atlas_path)
    build_sqlite_database(
        database_path=db_path,
        metadata=parsed.metadata,
        records=parsed.records,
    )
    return db_path


class FakeState:
    """Minimal state holder for endpoint tests."""

    def __init__(self, lookup_service: AtlasLookup) -> None:
        self.lookup_service = lookup_service


class FakeApp:
    """Minimal app holder exposing ``state`` like FastAPI."""

    def __init__(self, lookup_service: AtlasLookup) -> None:
        self.state = FakeState(lookup_service)


class FakeRequest:
    """Minimal request holder exposing ``app`` like FastAPI."""

    def __init__(self, lookup_service: AtlasLookup) -> None:
        self.app = FakeApp(lookup_service)


def make_request() -> FakeRequest:
    """Create a fake request backed by a temporary compiled atlas DB."""

    db_path = build_test_database()
    return FakeRequest(AtlasLookup(db_path))


def test_valid_normalization() -> None:
    payload = asyncio.run(
        normalize_birthtime(
            BirthtimeNormalizationRequest(
                date="2024-01-15",
                time="13:45",
                city="New York City",
            ),
            make_request(),
        )
    )

    assert payload["resolved_location"]["city"] == "New York City"
    assert payload["timezone"] == "America/New_York"
    assert payload["local_datetime"] == "2024-01-15T13:45:00-05:00"
    assert payload["utc_datetime"] == "2024-01-15T18:45:00+00:00"


def test_unknown_city_returns_404() -> None:
    try:
        asyncio.run(
            normalize_birthtime(
                BirthtimeNormalizationRequest(
                    date="2024-01-15",
                    time="13:45",
                    city="Atlantis",
                ),
                make_request(),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "No atlas match found" in exc.detail
    else:
        raise AssertionError("Expected 404 for unknown city")


def test_ambiguous_city_returns_409() -> None:
    try:
        asyncio.run(
            normalize_birthtime(
                BirthtimeNormalizationRequest(
                    date="2024-01-15",
                    time="13:45",
                    city="Springfield",
                ),
                make_request(),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Ambiguous city" in exc.detail["message"]
        assert len(exc.detail["candidates"]) == 3
    else:
        raise AssertionError("Expected 409 for ambiguous city")


def test_invalid_date_format_returns_422() -> None:
    try:
        asyncio.run(
            normalize_birthtime(
                BirthtimeNormalizationRequest(
                    date="15-01-2024",
                    time="13:45",
                    city="London",
                ),
                make_request(),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "date must be YYYY-MM-DD" in exc.detail
    else:
        raise AssertionError("Expected 422 for invalid date format")


def test_invalid_time_format_returns_422() -> None:
    try:
        asyncio.run(
            normalize_birthtime(
                BirthtimeNormalizationRequest(
                    date="2024-01-15",
                    time="1:45 PM",
                    city="London",
                ),
                make_request(),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "time must be HH:MM" in exc.detail
    else:
        raise AssertionError("Expected 422 for invalid time format")
