"""Tests for astrology geometry calculations."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import swisseph as swe

from src import astrology_geometry as ag
from src.astronomy import positions as ap


def stub_chiron(monkeypatch) -> None:
    """Use real Swiss Ephemeris for major bodies and stub Chiron only."""

    original_calculate_body_longitude = ap.calculate_body_longitude

    def patched_calculate_body_longitude(julian_day: float, body_code: int) -> float:
        if body_code == swe.AST_OFFSET + 2060:
            return 40.0
        return original_calculate_body_longitude(julian_day, body_code)

    original_calculate_body_coordinates = ap.calculate_body_coordinates

    def patched_calculate_body_coordinates(julian_day: float, body_code: int) -> tuple[float, float]:
        if body_code == swe.AST_OFFSET + 2060:
            return 40.0, 0.0
        return original_calculate_body_coordinates(julian_day, body_code)

    monkeypatch.setattr(ap, "calculate_body_longitude", patched_calculate_body_longitude)
    monkeypatch.setattr(ap, "calculate_body_coordinates", patched_calculate_body_coordinates)
    monkeypatch.setattr(ap, "configure_ephemeris_path", lambda: Path("."))
    monkeypatch.setattr(ag, "calculate_body_coordinates", patched_calculate_body_coordinates)
    monkeypatch.setattr(ag, "configure_ephemeris_path", lambda: Path("."))


def test_valid_house_calculation_uses_koch(monkeypatch) -> None:
    stub_chiron(monkeypatch)

    result = ag.calculate_astrology_geometry(
        utc_datetime="2024-01-15T13:45:00+00:00",
        latitude=51.5072,
        longitude=-0.1276,
    )

    assert result.requested_house_system == "K"
    assert result.actual_house_system == "K"
    assert result.fallback_reason is None
    assert len(result.houses) == 12
    assert result.houses[0].house == 1


def test_planetary_house_assignment(monkeypatch) -> None:
    stub_chiron(monkeypatch)

    result = ag.calculate_astrology_geometry(
        utc_datetime="2024-01-15T13:45:00+00:00",
        latitude=51.5072,
        longitude=-0.1276,
    )
    position_by_body = {position.body: position for position in result.positions}

    assert position_by_body["Sun"].house == 8
    assert position_by_body["Moon"].house == 10
    assert all(1 <= position.house <= 12 for position in result.positions)


def test_asc_mc_vertex_presence(monkeypatch) -> None:
    stub_chiron(monkeypatch)

    result = ag.calculate_astrology_geometry(
        utc_datetime="2024-01-15T13:45:00+00:00",
        latitude=51.5072,
        longitude=-0.1276,
    )

    assert result.ascendant.body == "Ascendant"
    assert result.midheaven.body == "Midheaven"
    assert result.vertex.body == "Vertex"


def test_wraparound_house_assignment() -> None:
    cusps = (330.0, 0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0)

    assert ag.determine_house_from_cusps(350.0, cusps) == 1
    assert ag.determine_house_from_cusps(15.0, cusps) == 2


def test_koch_failure_falls_back_to_porphyry(monkeypatch) -> None:
    stub_chiron(monkeypatch)

    result = ag.calculate_astrology_geometry(
        utc_datetime="2024-01-15T13:45:00+00:00",
        latitude=75.0,
        longitude=0.0,
    )

    assert result.requested_house_system == "K"
    assert result.actual_house_system == "O"
    assert result.fallback_reason is not None


def test_simulated_koch_failure_triggers_porphyry(monkeypatch) -> None:
    stub_chiron(monkeypatch)
    original_houses_ex = ag.swe.houses_ex

    def patched_houses_ex(julian_day: float, latitude: float, longitude: float, house_system: bytes):
        if house_system == b"K":
            raise ag.swe.Error("simulated Koch failure")
        return original_houses_ex(julian_day, latitude, longitude, house_system)

    monkeypatch.setattr(ag.swe, "houses_ex", patched_houses_ex)

    result = ag.calculate_astrology_geometry(
        utc_datetime="2024-01-15T13:45:00+00:00",
        latitude=51.5072,
        longitude=-0.1276,
    )

    assert result.actual_house_system == "O"
    assert result.fallback_reason == "simulated Koch failure"
