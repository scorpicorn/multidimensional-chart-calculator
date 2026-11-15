"""Shared data models for Atlas processing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AtlasMetadata:
    """Header metadata extracted from an Astrolog atlas source file."""

    source_tag: str
    declared_record_count: int
    comment_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AtlasRecord:
    """Canonical atlas row stored in the compiled lookup database."""

    record_id: int
    city: str
    city_norm: str
    region_code: str
    latitude: float
    longitude_astrolog: float
    longitude_standard: float
    timezone: str
