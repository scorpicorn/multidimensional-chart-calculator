"""Astronomical position helpers backed by Swiss Ephemeris."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import os
from pathlib import Path

try:
    import swisseph as swe
except ImportError:  # pragma: no cover - exercised through runtime error handling
    swe = None


SWISS_FLAGS = (
    (getattr(swe, "FLG_SWIEPH", 0) | getattr(swe, "FLG_SPEED", 0)) if swe is not None else 0
)
BODY_SEQUENCE: tuple[tuple[str, int], ...] = (
    ("Sun", 0),
    ("Moon", 1),
    ("North Node", 11),
    ("Mercury", 2),
    ("Venus", 3),
    ("Mars", 4),
    ("Jupiter", 5),
    ("Saturn", 6),
    ("Uranus", 7),
    ("Neptune", 8),
    ("Pluto", 9),
)
ZODIAC_SIGNS: tuple[str, ...] = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)


class SwissEphemerisUnavailableError(RuntimeError):
    """Raised when Swiss Ephemeris is not installed."""


class EphemerisDataError(RuntimeError):
    """Raised when required ephemeris data files are unavailable."""


@dataclass(frozen=True, slots=True)
class PlanetPosition:
    """A single ecliptic longitude result."""

    body: str
    longitude: float


@dataclass(frozen=True, slots=True)
class ZodiacPosition:
    """A planetary position expressed as sign, degree, and minutes."""

    body: str
    longitude_decimal: float
    sign: str
    degree: int
    minutes: int


def normalize_longitude(value: float) -> float:
    """Normalize a longitude into the 0-360 degree range."""

    return value % 360.0


def longitude_to_zodiac_position(body: str, longitude: float) -> ZodiacPosition:
    """Convert a 0-360 longitude into zodiac sign, degree, and minutes."""

    normalized_longitude = normalize_longitude(longitude)
    sign_index = int(normalized_longitude // 30)
    sign = ZODIAC_SIGNS[sign_index]
    longitude_within_sign = normalized_longitude % 30.0
    degree = math.floor(longitude_within_sign)
    fractional_degree = longitude_within_sign - degree
    minutes = math.floor(fractional_degree * 60)
    return ZodiacPosition(
        body=body,
        longitude_decimal=normalized_longitude,
        sign=sign,
        degree=degree,
        minutes=minutes,
    )


def default_ephemeris_path() -> Path:
    """Return the configured Swiss Ephemeris directory."""

    configured_path = os.environ.get("SWISSEPH_PATH")
    if configured_path:
        return Path(configured_path)
    return Path(__file__).resolve().parents[2] / "data" / "ephe"


def configure_ephemeris_path() -> Path:
    """Configure Swiss Ephemeris to use the selected ephemeris directory."""

    if swe is None:
        raise SwissEphemerisUnavailableError(
            "Swiss Ephemeris is not installed. Install pyswisseph first."
        )

    ephemeris_path = default_ephemeris_path()
    swe.set_ephe_path(str(ephemeris_path))
    return ephemeris_path


def parse_utc_datetime(value: str) -> datetime:
    """Parse an ISO datetime string and normalize it to UTC."""

    normalized_value = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized_value)
    except ValueError as exc:
        raise ValueError("utc_datetime must be a valid ISO datetime string.") from exc

    if parsed.tzinfo is None:
        raise ValueError("utc_datetime must include a timezone offset or Z suffix.")
    return parsed.astimezone(timezone.utc)


def julian_day_from_utc(value: str) -> float:
    """Convert an ISO UTC datetime string into a Julian Day."""

    utc_datetime = parse_utc_datetime(value)
    hour = (
        utc_datetime.hour
        + utc_datetime.minute / 60
        + utc_datetime.second / 3600
        + utc_datetime.microsecond / 3_600_000_000
    )
    return swe.julday(utc_datetime.year, utc_datetime.month, utc_datetime.day, hour)


def calculate_body_longitude(julian_day: float, body_code: int) -> float:
    """Calculate one body's ecliptic longitude with Swiss Ephemeris."""

    try:
        result, _ = swe.calc_ut(julian_day, body_code, SWISS_FLAGS)
    except swe.Error as exc:
        raise EphemerisDataError(str(exc)) from exc
    return normalize_longitude(float(result[0]))


def calculate_body_coordinates(julian_day: float, body_code: int) -> tuple[float, float]:
    """Calculate ecliptic longitude and latitude for one body."""

    try:
        result, _ = swe.calc_ut(julian_day, body_code, SWISS_FLAGS)
    except swe.Error as exc:
        raise EphemerisDataError(str(exc)) from exc
    return normalize_longitude(float(result[0])), float(result[1])


def derive_additional_positions(positions: list[PlanetPosition]) -> list[PlanetPosition]:
    """Add Earth and South Node and return the final display order."""

    longitude_by_body = {position.body: position.longitude for position in positions}
    position_by_body = {position.body: position for position in positions}
    position_by_body["Earth"] = PlanetPosition(
        "Earth",
        normalize_longitude(longitude_by_body["Sun"] + 180.0),
    )
    position_by_body["South Node"] = PlanetPosition(
        "South Node",
        normalize_longitude(longitude_by_body["North Node"] + 180.0),
    )
    ordered_bodies = (
        "Sun",
        "Earth",
        "North Node",
        "South Node",
        "Moon",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
        "Chiron",
    )
    return [position_by_body[body_name] for body_name in ordered_bodies]


def calculate_planetary_positions(
    *,
    utc_datetime: str,
    latitude: float,
    longitude: float,
) -> list[PlanetPosition]:
    """Calculate planetary longitudes for a normalized UTC birthtime.

    Latitude and longitude are accepted for API compatibility and future extension.
    The current planetary calculations are geocentric and do not use them directly.
    """

    _ = (latitude, longitude)
    configure_ephemeris_path()
    julian_day = julian_day_from_utc(utc_datetime)

    positions = [
        PlanetPosition(body_name, calculate_body_longitude(julian_day, body_code))
        for body_name, body_code in BODY_SEQUENCE
    ]
    chiron_code = swe.AST_OFFSET + 2060
    positions.append(PlanetPosition("Chiron", calculate_body_longitude(julian_day, chiron_code)))
    return derive_additional_positions(positions)


def calculate_zodiac_positions(
    *,
    utc_datetime: str,
    latitude: float,
    longitude: float,
) -> list[ZodiacPosition]:
    """Calculate planetary positions and convert them to zodiac notation."""

    positions = calculate_planetary_positions(
        utc_datetime=utc_datetime,
        latitude=latitude,
        longitude=longitude,
    )
    return [
        longitude_to_zodiac_position(position.body, position.longitude)
        for position in positions
    ]
