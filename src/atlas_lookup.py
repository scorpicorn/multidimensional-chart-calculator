"""Runtime lookup API for the compiled Atlas SQLite database."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .atlas_index import (
    load_compiled_atlas,
    load_records_by_id,
    lookup_record_ids_by_city,
    lookup_record_ids_by_city_region,
    lookup_record_ids_by_prefix,
    normalize_region_code,
)
from .atlas_parser import normalize_city_name
from .models import AtlasRecord


class AtlasLookup:
    """Query helper for the compiled offline atlas database."""

    def __init__(self, database_path: str | Path) -> None:
        """Load the compiled atlas artifact at startup."""

        self.compiled_atlas = load_compiled_atlas(database_path)

    def lookup_exact(
        self,
        city: str,
        region_code: str | None = None,
    ) -> list[AtlasRecord]:
        """Return deterministic exact-match candidates for a city query.

        When ``region_code`` is provided, city+region exact matches are returned
        first, followed by the remaining exact-city matches in stable order.
        """

        city_norm = normalize_city_name(city)
        city_record_ids = lookup_record_ids_by_city(self.compiled_atlas, city_norm)

        if region_code is None:
            return self._fetch_records(city_record_ids)

        prioritized_ids = lookup_record_ids_by_city_region(
            self.compiled_atlas,
            city_norm,
            normalize_region_code(region_code),
        )
        prioritized_id_set = set(prioritized_ids)
        ordered_ids = prioritized_ids + [
            record_id for record_id in city_record_ids if record_id not in prioritized_id_set
        ]
        return self._fetch_records(ordered_ids)

    def lookup_prefix(self, prefix: str, limit: int = 20) -> list[AtlasRecord]:
        """Return normalized prefix matches ordered for stable browsing."""

        record_ids = lookup_record_ids_by_prefix(
            self.compiled_atlas,
            normalize_city_name(prefix),
            limit,
        )
        return self._fetch_records(record_ids)

    def _fetch_records(self, record_ids: Sequence[int]) -> list[AtlasRecord]:
        """Load atlas records from the compiled artifact in the given order."""

        rows = load_records_by_id(self.compiled_atlas, record_ids)
        return [row_to_record(row) for row in rows]

    def lookup_city(self, city: str) -> list[AtlasRecord]:
        """Backward-compatible alias for exact city lookup."""

        return self.lookup_exact(city)

    def lookup_city_region(self, city: str, region_code: str) -> list[AtlasRecord]:
        """Backward-compatible alias for exact city+region lookup."""

        return self.lookup_exact(city, region_code)


def row_to_record(row: object) -> AtlasRecord:
    """Convert a SQLite row object into an AtlasRecord."""

    return AtlasRecord(
        record_id=int(row["record_id"]),
        city=str(row["city"]),
        city_norm=str(row["city_norm"]),
        region_code=str(row["region_code"]),
        latitude=float(row["latitude"]),
        longitude_astrolog=float(row["longitude_astrolog"]),
        longitude_standard=float(row["longitude_standard"]),
        timezone=str(row["timezone"]),
    )
