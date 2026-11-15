"""Minimal FastAPI app for the compiled Atlas lookup service."""

from __future__ import annotations

from datetime import datetime
import os
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .atlas_lookup import AtlasLookup
from .atlas_index import normalize_region_code
from .build_atlas_db import default_database_path
from .models import AtlasRecord
from .astrology_geometry import AstrologyGeometryResult, HouseCusp, PositionedBody, calculate_astrology_geometry
from .planetary_positions import (
    EphemerisDataError,
    PlanetPosition,
    SwissEphemerisUnavailableError,
    ZodiacPosition,
)


class PrettyJSONResponse(Response):
    """Render JSON with indentation for easier browser reading."""

    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        """Serialize JSON content with stable indentation."""

        return json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")


class BirthtimeNormalizationRequest(BaseModel):
    """Request body for birthtime normalization."""

    date: str = Field(..., description="Date in YYYY-MM-DD format.")
    time: str = Field(..., description="Time in HH:MM 24-hour format.")
    city: str = Field(..., min_length=1, description="Birth city.")
    region_code: str | None = Field(default=None, description="Optional region code.")


class PositionCalculationRequest(BaseModel):
    """Request body for planetary position calculation."""

    utc_datetime: str = Field(..., description="UTC datetime as an ISO string.")
    latitude: float = Field(..., description="Latitude in decimal degrees.")
    longitude: float = Field(..., description="Longitude in decimal degrees.")


def compiled_database_path() -> Path:
    """Return the compiled atlas database path for the API process."""

    configured_path = os.environ.get("ATLAS_DB_PATH")
    if configured_path:
        return Path(configured_path)
    return default_database_path()


def record_to_api_payload(record: AtlasRecord) -> dict[str, Any]:
    """Convert an atlas record into a JSON-friendly API payload."""

    return {
        "record_id": record.record_id,
        "city": record.city,
        "region_code": record.region_code,
        "latitude": record.latitude,
        "longitude_standard": record.longitude_standard,
        "timezone": record.timezone,
    }


def position_to_api_payload(position: PlanetPosition) -> dict[str, Any]:
    """Convert a planetary position to a JSON-friendly payload."""

    return {
        "body": position.body,
        "longitude": round(position.longitude, 6),
    }


def zodiac_position_to_api_payload(position: ZodiacPosition) -> dict[str, Any]:
    """Convert a zodiac position to the public API response format."""

    return {
        "body": position.body,
        "longitude_decimal": position.longitude_decimal,
        "sign": position.sign,
        "degree": position.degree,
        "minutes": position.minutes,
    }


def house_cusp_to_api_payload(cusp: HouseCusp) -> dict[str, Any]:
    """Convert a house cusp to the public API response format."""

    return {
        "house": cusp.house,
        "longitude_decimal": cusp.longitude_decimal,
        "sign": cusp.sign,
        "degree": cusp.degree,
        "minutes": cusp.minutes,
    }


def positioned_body_to_api_payload(position: PositionedBody) -> dict[str, Any]:
    """Convert a positioned planetary body to the public API response format."""

    return {
        "body": position.body,
        "longitude_decimal": position.longitude_decimal,
        "sign": position.sign,
        "degree": position.degree,
        "minutes": position.minutes,
        "house": position.house,
    }


def astrology_geometry_to_api_payload(result: AstrologyGeometryResult) -> dict[str, Any]:
    """Convert astrology geometry to the public API response format."""

    return {
        "requested_house_system": result.requested_house_system,
        "actual_house_system": result.actual_house_system,
        "fallback_reason": result.fallback_reason,
        "ascendant": zodiac_position_to_api_payload(result.ascendant),
        "midheaven": zodiac_position_to_api_payload(result.midheaven),
        "vertex": zodiac_position_to_api_payload(result.vertex),
        "houses": [house_cusp_to_api_payload(cusp) for cusp in result.houses],
        "positions": [positioned_body_to_api_payload(position) for position in result.positions],
    }


def normalize_birthtime_payload(
    *,
    date_value: str,
    time_value: str,
    record: AtlasRecord,
) -> dict[str, Any]:
    """Convert local birthtime input into normalized UTC output."""

    try:
        local_naive = datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="date must be YYYY-MM-DD and time must be HH:MM in 24-hour format.",
        ) from exc

    try:
        timezone = ZoneInfo(record.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Timezone data is unavailable for {record.timezone}.",
        ) from exc

    local_datetime = local_naive.replace(tzinfo=timezone)
    utc_datetime = local_datetime.astimezone(ZoneInfo("UTC"))
    return {
        "resolved_location": record_to_api_payload(record),
        "timezone": record.timezone,
        "local_datetime": local_datetime.isoformat(),
        "utc_datetime": utc_datetime.isoformat(),
    }


def resolve_birth_location(
    lookup_service: AtlasLookup,
    *,
    city: str,
    region_code: str | None,
) -> AtlasRecord:
    """Resolve a city query to a single atlas record or raise a clear API error."""

    candidates = lookup_service.lookup_exact(city, region_code)
    if region_code is None:
        if not candidates:
            raise HTTPException(status_code=404, detail=f"No atlas match found for city '{city}'.")
        if len(candidates) > 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"Ambiguous city '{city}'.",
                    "candidates": [record_to_api_payload(record) for record in candidates],
                },
            )
        return candidates[0]

    region_candidates = [
        record
        for record in candidates
        if normalize_region_code(record.region_code) == normalize_region_code(region_code)
    ]
    if not region_candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No atlas match found for city '{city}' in region '{region_code}'.",
        )
    if len(region_candidates) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Ambiguous city '{city}' in region '{region_code}'.",
                "candidates": [record_to_api_payload(record) for record in region_candidates],
            },
        )
    return region_candidates[0]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the compiled atlas lookup service when the app starts."""

    database_path = compiled_database_path()
    if not database_path.exists():
        raise RuntimeError(
            "Compiled atlas database not found. "
            f"Expected artifact at {database_path}."
        )

    app.state.lookup_service = AtlasLookup(database_path)
    yield


app = FastAPI(title="Atlas Lookup API", version="0.1.0", lifespan=lifespan)


def get_lookup_service(request: Request) -> AtlasLookup:
    """Return the startup-loaded lookup service from application state."""

    lookup_service = getattr(request.app.state, "lookup_service", None)
    if lookup_service is None:
        raise HTTPException(status_code=503, detail="Lookup service is not available.")
    return lookup_service


@app.get("/lookup/exact", response_class=PrettyJSONResponse)
async def lookup_exact(
    request: Request,
    city: str = Query(..., min_length=1, max_length=200),
    region_code: str | None = Query(default=None, min_length=1, max_length=32),
) -> dict[str, Any]:
    """Return exact-match atlas candidates for a city query."""

    lookup_service = get_lookup_service(request)
    normalized_city = city.strip()
    if not normalized_city:
        raise HTTPException(status_code=422, detail="city must not be blank.")

    if region_code is not None and not region_code.strip():
        raise HTTPException(status_code=422, detail="region_code must not be blank.")

    results = lookup_service.lookup_exact(normalized_city, region_code)
    return {
        "query": {
            "city": normalized_city,
            "region_code": region_code.strip() if region_code is not None else None,
        },
        "count": len(results),
        "results": [record_to_api_payload(record) for record in results],
    }


@app.get("/lookup/prefix", response_class=PrettyJSONResponse)
async def lookup_prefix(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Return prefix-match atlas candidates for a city query."""

    lookup_service = get_lookup_service(request)
    normalized_prefix = q.strip()
    if not normalized_prefix:
        raise HTTPException(status_code=422, detail="q must not be blank.")

    results = lookup_service.lookup_prefix(normalized_prefix, limit=limit)
    return {
        "query": {
            "q": normalized_prefix,
            "limit": limit,
        },
        "count": len(results),
        "results": [record_to_api_payload(record) for record in results],
    }


@app.post("/normalize-birthtime", response_class=PrettyJSONResponse)
async def normalize_birthtime(
    payload: BirthtimeNormalizationRequest,
    request: Request,
) -> dict[str, Any]:
    """Resolve a birth location and convert local date/time to UTC."""

    lookup_service = get_lookup_service(request)
    city = payload.city.strip()
    if not city:
        raise HTTPException(status_code=422, detail="city must not be blank.")

    region_code = payload.region_code.strip() if payload.region_code is not None else None
    if payload.region_code is not None and not region_code:
        raise HTTPException(status_code=422, detail="region_code must not be blank.")

    record = resolve_birth_location(
        lookup_service,
        city=city,
        region_code=region_code,
    )
    normalized = normalize_birthtime_payload(
        date_value=payload.date,
        time_value=payload.time,
        record=record,
    )
    return {
        "input": {
            "date": payload.date,
            "time": payload.time,
            "city": city,
            "region_code": region_code,
        },
        **normalized,
    }


@app.post("/calculate-positions", response_class=PrettyJSONResponse)
async def calculate_positions(
    payload: PositionCalculationRequest,
) -> dict[str, Any]:
    """Calculate astrology geometry and planetary zodiac positions from UTC input."""

    try:
        result = calculate_astrology_geometry(
            utc_datetime=payload.utc_datetime,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SwissEphemerisUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except EphemerisDataError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Swiss Ephemeris data files are missing or incomplete. "
                f"{exc}"
            ),
        ) from exc

    return astrology_geometry_to_api_payload(result)
