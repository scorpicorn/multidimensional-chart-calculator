"""Tests for Swiss Ephemeris planetary position calculation."""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import swisseph as swe

from src import planetary_positions
from src.astronomy import positions as astronomy_positions


def test_longitude_to_zodiac_position_uses_floor_logic() -> None:
    position = planetary_positions.longitude_to_zodiac_position("Sun", 294.892955)

    assert position.body == "Sun"
    assert position.longitude_decimal == 294.892955
    assert position.sign == "Capricorn"
    assert position.degree == 24
    assert position.minutes == 53


def test_calculate_zodiac_positions_known_date(monkeypatch) -> None:
    """Use Swiss Ephemeris for major bodies and stub Chiron for a known UTC date."""

    original_calculate_body_longitude = astronomy_positions.calculate_body_longitude

    def patched_calculate_body_longitude(julian_day: float, body_code: int) -> float:
        if body_code == swe.AST_OFFSET + 2060:
            return 40.0
        return original_calculate_body_longitude(julian_day, body_code)

    monkeypatch.setattr(astronomy_positions, "configure_ephemeris_path", lambda: Path("."))
    monkeypatch.setattr(
        astronomy_positions,
        "calculate_body_longitude",
        patched_calculate_body_longitude,
    )

    positions = planetary_positions.calculate_zodiac_positions(
        utc_datetime="2024-01-15T13:45:00+00:00",
        latitude=51.5085,
        longitude=-0.1257,
    )
    position_by_body = {position.body: position for position in positions}

    assert abs(position_by_body["Sun"].longitude_decimal - 294.892955) < 1e-6
    assert position_by_body["Sun"].sign == "Capricorn"
    assert position_by_body["Sun"].degree == 24
    assert position_by_body["Sun"].minutes == 53
    assert abs(position_by_body["Moon"].longitude_decimal - 350.950444) < 1e-6
    assert position_by_body["Moon"].sign == "Pisces"
    assert position_by_body["Moon"].degree == 20
    assert position_by_body["Moon"].minutes == 57
    assert abs(position_by_body["North Node"].longitude_decimal - 19.612295) < 1e-6
    assert position_by_body["North Node"].sign == "Aries"
    assert position_by_body["North Node"].degree == 19
    assert position_by_body["North Node"].minutes == 36
    assert abs(position_by_body["Earth"].longitude_decimal - 114.892955) < 1e-6
    assert position_by_body["Earth"].sign == "Cancer"
    assert position_by_body["Earth"].degree == 24
    assert position_by_body["Earth"].minutes == 53
    assert abs(position_by_body["South Node"].longitude_decimal - 199.612295) < 1e-6
    assert position_by_body["South Node"].sign == "Libra"
    assert position_by_body["South Node"].degree == 19
    assert position_by_body["South Node"].minutes == 36
    assert position_by_body["Chiron"].longitude_decimal == 40.0
    assert position_by_body["Chiron"].sign == "Taurus"
    assert position_by_body["Chiron"].degree == 10
    assert position_by_body["Chiron"].minutes == 0
