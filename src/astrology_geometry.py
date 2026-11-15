"""Astrology geometry helpers for houses, angles, and house placement."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .astronomy.positions import (
    EphemerisDataError,
    BODY_SEQUENCE,
    PlanetPosition,
    ZodiacPosition,
    calculate_body_coordinates,
    calculate_planetary_positions,
    configure_ephemeris_path,
    julian_day_from_utc,
    longitude_to_zodiac_position,
    normalize_longitude,
    swe,
)

PRIMARY_HOUSE_SYSTEM = "K"
FALLBACK_HOUSE_SYSTEM = "O"


@dataclass(frozen=True, slots=True)
class HouseCusp:
    """A house cusp with formatted zodiac output."""

    house: int
    longitude_decimal: float
    sign: str
    degree: int
    minutes: int


@dataclass(frozen=True, slots=True)
class PositionedBody:
    """A zodiac position with house placement."""

    body: str
    longitude_decimal: float
    sign: str
    degree: int
    minutes: int
    house: int


@dataclass(frozen=True, slots=True)
class AstrologyGeometryResult:
    """Calculated astrology geometry payload."""

    requested_house_system: str
    actual_house_system: str
    fallback_reason: str | None
    ascendant: ZodiacPosition
    midheaven: ZodiacPosition
    vertex: ZodiacPosition
    houses: tuple[HouseCusp, ...]
    positions: tuple[PositionedBody, ...]


def longitude_within_house(longitude: float, start: float, end: float) -> bool:
    """Return whether a longitude lies within a house cusp interval."""

    normalized_longitude = normalize_longitude(longitude)
    normalized_start = normalize_longitude(start)
    normalized_end = normalize_longitude(end)
    if normalized_start <= normalized_end:
        return normalized_start <= normalized_longitude < normalized_end
    return normalized_longitude >= normalized_start or normalized_longitude < normalized_end


def build_house_cusps(cusps: tuple[float, ...]) -> tuple[HouseCusp, ...]:
    """Convert raw house cusp longitudes into formatted cusp models."""

    house_cusps: list[HouseCusp] = []
    for house_number, longitude in enumerate(cusps, start=1):
        zodiac = longitude_to_zodiac_position(f"House {house_number}", longitude)
        house_cusps.append(
            HouseCusp(
                house=house_number,
                longitude_decimal=zodiac.longitude_decimal,
                sign=zodiac.sign,
                degree=zodiac.degree,
                minutes=zodiac.minutes,
            )
        )
    return tuple(house_cusps)


def determine_house_from_cusps(longitude: float, cusps: tuple[float, ...]) -> int:
    """Assign a longitude to a house using cusp boundaries with wraparound handling."""

    for index in range(12):
        start = cusps[index]
        end = cusps[(index + 1) % 12]
        if longitude_within_house(longitude, start, end):
            return index + 1
    return 12


def validate_house_cusps(cusps: tuple[float, ...]) -> bool:
    """Check that a cusp set contains 12 usable longitudes."""

    return len(cusps) == 12 and all(math.isfinite(cusp) for cusp in cusps)


def calculate_obliquity(julian_day: float) -> float:
    """Return true obliquity in degrees for house position calculations."""

    try:
        result, _ = swe.calc_ut(julian_day, swe.ECL_NUT, 0)
    except swe.Error as exc:
        raise EphemerisDataError(str(exc)) from exc
    return float(result[0])


def body_code_for_name(body_name: str) -> int | None:
    """Return the Swiss Ephemeris body code for a named body when available."""

    name_to_code = dict(BODY_SEQUENCE)
    if body_name == "Chiron":
        return swe.AST_OFFSET + 2060
    return name_to_code.get(body_name)


def calculate_house_data(
    julian_day: float,
    latitude: float,
    longitude: float,
) -> tuple[str, tuple[float, ...], tuple[float, ...], str | None]:
    """Calculate house cusps and angles with Koch fallback to Porphyry."""

    fallback_reason: str | None = None
    for house_system in (PRIMARY_HOUSE_SYSTEM, FALLBACK_HOUSE_SYSTEM):
        try:
            cusps, ascmc = swe.houses_ex(julian_day, latitude, longitude, house_system.encode("ascii"))
        except swe.Error as exc:
            if house_system == PRIMARY_HOUSE_SYSTEM:
                fallback_reason = str(exc)
                continue
            raise EphemerisDataError(str(exc)) from exc

        cusp_tuple = tuple(float(cusp) for cusp in cusps)
        ascmc_tuple = tuple(float(value) for value in ascmc)
        if validate_house_cusps(cusp_tuple):
            return house_system, cusp_tuple, ascmc_tuple, fallback_reason
        if house_system == PRIMARY_HOUSE_SYSTEM:
            fallback_reason = "Koch produced invalid house cusps."

    raise EphemerisDataError("Unable to calculate valid house cusps with Koch or Porphyry.")


def build_positioned_bodies(
    planet_positions: list[PlanetPosition],
    cusps: tuple[float, ...],
    julian_day: float,
    latitude: float,
    actual_house_system: str,
    armc: float,
) -> tuple[PositionedBody, ...]:
    """Attach house placement to each planetary zodiac position."""

    obliquity = calculate_obliquity(julian_day)
    positioned: list[PositionedBody] = []
    for position in planet_positions:
        zodiac = longitude_to_zodiac_position(position.body, position.longitude)
        body_code = body_code_for_name(position.body)
        house_number = determine_house_from_cusps(position.longitude, cusps)
        if body_code is not None:
            body_longitude, body_latitude = calculate_body_coordinates(julian_day, body_code)
            try:
                raw_house = swe.house_pos(
                    armc,
                    latitude,
                    obliquity,
                    (body_longitude, body_latitude),
                    actual_house_system.encode("ascii"),
                )
                if math.isfinite(raw_house):
                    computed_house = int(math.floor(raw_house))
                    if 1 <= computed_house <= 12:
                        house_number = computed_house
            except swe.Error:
                house_number = determine_house_from_cusps(position.longitude, cusps)
        positioned.append(
            PositionedBody(
                body=zodiac.body,
                longitude_decimal=zodiac.longitude_decimal,
                sign=zodiac.sign,
                degree=zodiac.degree,
                minutes=zodiac.minutes,
                house=house_number,
            )
        )
    return tuple(positioned)


def build_angle_position(name: str, longitude: float) -> ZodiacPosition:
    """Build a formatted angle position."""

    return longitude_to_zodiac_position(name, longitude)


def calculate_astrology_geometry(
    *,
    utc_datetime: str,
    latitude: float,
    longitude: float,
) -> AstrologyGeometryResult:
    """Calculate astrology geometry using Koch houses with Porphyry fallback."""

    configure_ephemeris_path()
    julian_day = julian_day_from_utc(utc_datetime)
    actual_house_system, cusps, ascmc, fallback_reason = calculate_house_data(
        julian_day,
        latitude,
        longitude,
    )
    _ = calculate_obliquity(julian_day)
    planet_positions = calculate_planetary_positions(
        utc_datetime=utc_datetime,
        latitude=latitude,
        longitude=longitude,
    )
    return AstrologyGeometryResult(
        requested_house_system=PRIMARY_HOUSE_SYSTEM,
        actual_house_system=actual_house_system,
        fallback_reason=fallback_reason,
        ascendant=build_angle_position("Ascendant", ascmc[swe.ASC]),
        midheaven=build_angle_position("Midheaven", ascmc[swe.MC]),
        vertex=build_angle_position("Vertex", ascmc[swe.VERTEX]),
        houses=build_house_cusps(cusps),
        positions=build_positioned_bodies(
            planet_positions,
            cusps,
            julian_day,
            latitude,
            actual_house_system,
            ascmc[2],
        ),
    )
