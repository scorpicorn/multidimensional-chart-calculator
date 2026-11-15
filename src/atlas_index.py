"""SQLite schema and build helpers for Atlas lookup data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .models import AtlasMetadata, AtlasRecord

MAX_PREFIX_LENGTH = 10

SCHEMA_SQL = """
PRAGMA journal_mode = DELETE;

DROP TABLE IF EXISTS atlas_metadata;
DROP TABLE IF EXISTS atlas_records;
DROP TABLE IF EXISTS atlas_city_index;
DROP TABLE IF EXISTS atlas_city_region_index;
DROP TABLE IF EXISTS atlas_prefix_index;

CREATE TABLE atlas_metadata (
    source_tag TEXT NOT NULL,
    declared_record_count INTEGER NOT NULL,
    comment_blob TEXT NOT NULL
);

CREATE TABLE atlas_records (
    record_id INTEGER PRIMARY KEY,
    city TEXT NOT NULL,
    city_norm TEXT NOT NULL,
    region_code TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude_astrolog REAL NOT NULL,
    longitude_standard REAL NOT NULL,
    timezone TEXT NOT NULL
);

CREATE TABLE atlas_city_index (
    city_norm TEXT NOT NULL,
    record_id INTEGER NOT NULL REFERENCES atlas_records (record_id)
);

CREATE TABLE atlas_city_region_index (
    city_norm TEXT NOT NULL,
    region_code_norm TEXT NOT NULL,
    record_id INTEGER NOT NULL REFERENCES atlas_records (record_id)
);

CREATE TABLE atlas_prefix_index (
    prefix TEXT NOT NULL,
    record_id INTEGER NOT NULL REFERENCES atlas_records (record_id)
);

CREATE INDEX idx_atlas_city_index_city_norm
    ON atlas_city_index (city_norm, record_id);

CREATE INDEX idx_atlas_city_region_index_key
    ON atlas_city_region_index (city_norm, region_code_norm, record_id);

CREATE INDEX idx_atlas_prefix_index_prefix
    ON atlas_prefix_index (prefix, record_id);
"""


@dataclass(frozen=True, slots=True)
class CompiledAtlas:
    """Runtime handle for the compiled atlas artifact."""

    database_path: Path


def normalize_region_code(value: str) -> str:
    """Normalize region codes for exact indexed lookups."""

    return value.strip().lower()


def build_prefixes(value: str, max_length: int = MAX_PREFIX_LENGTH) -> tuple[str, ...]:
    """Build ordered prefixes for a normalized city name up to ``max_length``."""

    capped_length = min(len(value), max_length)
    return tuple(value[:prefix_length] for prefix_length in range(1, capped_length + 1))


def connect_sqlite(path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection configured for named-row access."""

    connection = sqlite3.connect(Path(path))
    connection.row_factory = sqlite3.Row
    return connection


def build_sqlite_database(
    *,
    database_path: str | Path,
    metadata: AtlasMetadata,
    records: Iterable[AtlasRecord],
) -> None:
    """Create a compiled SQLite lookup database from parsed atlas data."""

    target_path = Path(database_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    record_list = list(records)

    with connect_sqlite(target_path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            """
            INSERT INTO atlas_metadata (source_tag, declared_record_count, comment_blob)
            VALUES (?, ?, ?)
            """,
            (
                metadata.source_tag,
                metadata.declared_record_count,
                "\n".join(metadata.comment_lines),
            ),
        )
        connection.executemany(
            """
            INSERT INTO atlas_records (
                record_id,
                city,
                city_norm,
                region_code,
                latitude,
                longitude_astrolog,
                longitude_standard,
                timezone
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    record.record_id,
                    record.city,
                    record.city_norm,
                    record.region_code,
                    record.latitude,
                    record.longitude_astrolog,
                    record.longitude_standard,
                    record.timezone,
                )
                for record in record_list
            ),
        )
        connection.executemany(
            """
            INSERT INTO atlas_city_index (city_norm, record_id)
            VALUES (?, ?)
            """,
            ((record.city_norm, record.record_id) for record in record_list),
        )
        connection.executemany(
            """
            INSERT INTO atlas_city_region_index (city_norm, region_code_norm, record_id)
            VALUES (?, ?, ?)
            """,
            (
                (
                    record.city_norm,
                    normalize_region_code(record.region_code),
                    record.record_id,
                )
                for record in record_list
            ),
        )
        connection.executemany(
            """
            INSERT INTO atlas_prefix_index (prefix, record_id)
            VALUES (?, ?)
            """,
            (
                (prefix, record.record_id)
                for record in record_list
                for prefix in build_prefixes(record.city_norm)
            ),
        )
        connection.commit()


def load_compiled_atlas(path: str | Path) -> CompiledAtlas:
    """Return a runtime handle for a compiled atlas artifact."""

    return CompiledAtlas(database_path=Path(path))


def lookup_record_ids_by_city(compiled_atlas: CompiledAtlas, city_norm: str) -> list[int]:
    """Load record ids for an exact normalized city match."""

    with connect_sqlite(compiled_atlas.database_path) as connection:
        rows = connection.execute(
            """
            SELECT record_id
            FROM atlas_city_index
            WHERE city_norm = ?
            ORDER BY record_id
            """,
            (city_norm,),
        ).fetchall()
    return [int(row["record_id"]) for row in rows]


def lookup_record_ids_by_city_region(
    compiled_atlas: CompiledAtlas,
    city_norm: str,
    region_code_norm: str,
) -> list[int]:
    """Load record ids for an exact normalized city and region match."""

    with connect_sqlite(compiled_atlas.database_path) as connection:
        rows = connection.execute(
            """
            SELECT record_id
            FROM atlas_city_region_index
            WHERE city_norm = ? AND region_code_norm = ?
            ORDER BY record_id
            """,
            (city_norm, region_code_norm),
        ).fetchall()
    return [int(row["record_id"]) for row in rows]


def lookup_record_ids_by_prefix(
    compiled_atlas: CompiledAtlas,
    prefix: str,
    limit: int = 25,
) -> list[int]:
    """Load record ids for a normalized prefix match."""

    with connect_sqlite(compiled_atlas.database_path) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT record_id
            FROM atlas_prefix_index
            WHERE prefix = ?
            ORDER BY record_id
            LIMIT ?
            """,
            (prefix[:MAX_PREFIX_LENGTH], limit),
        ).fetchall()
    return [int(row["record_id"]) for row in rows]


def load_records_by_id(
    compiled_atlas: CompiledAtlas,
    record_ids: Sequence[int],
) -> list[sqlite3.Row]:
    """Load record rows from the master record store by record id order."""

    if not record_ids:
        return []

    placeholders = ", ".join("?" for _ in record_ids)
    with connect_sqlite(compiled_atlas.database_path) as connection:
        rows = connection.execute(
            f"""
            SELECT record_id, city, city_norm, region_code, latitude,
                   longitude_astrolog, longitude_standard, timezone
            FROM atlas_records
            WHERE record_id IN ({placeholders})
            """,
            tuple(record_ids),
        ).fetchall()
    row_by_id = {int(row["record_id"]): row for row in rows}
    return [row_by_id[record_id] for record_id in record_ids if record_id in row_by_id]
