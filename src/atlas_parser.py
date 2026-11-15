"""Build-time parser for Astrolog atlas source files."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from .models import AtlasMetadata, AtlasRecord

COUNT_LINE_PREFIX = "-YY "
PUNCTUATION_RE = re.compile(r"[^\w\s]")
WHITESPACE_RE = re.compile(r"\s+")


class AtlasParseError(ValueError):
    """Raised when the atlas source cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class ParsedAtlas:
    """Parsed atlas metadata and canonical records."""

    metadata: AtlasMetadata
    records: tuple[AtlasRecord, ...]


def normalize_city_name(value: str) -> str:
    """Normalize a city name into a stable, accent-insensitive search key."""

    lowered = value.lower().strip()
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    without_punctuation = PUNCTUATION_RE.sub(" ", without_accents)
    collapsed = WHITESPACE_RE.sub(" ", without_punctuation).strip()
    return collapsed


def astrolog_to_standard_longitude(value: float) -> float:
    """Convert Astrolog longitudes into standard geographic longitudes."""

    return -value


def should_skip_line(line: str) -> bool:
    """Return whether a raw atlas line is blank or metadata."""

    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith(";")
        or stripped.startswith("@")
        or stripped.startswith(COUNT_LINE_PREFIX)
    )


def parse_declared_record_count(line: str) -> int | None:
    """Extract the declared record count from a metadata line if present."""

    stripped = line.strip()
    if not stripped.startswith(COUNT_LINE_PREFIX):
        return None
    try:
        return int(stripped[len(COUNT_LINE_PREFIX) :].strip())
    except ValueError as exc:
        raise AtlasParseError(f"Invalid record count line: {stripped!r}") from exc


def iter_data_lines(lines: Iterable[str]) -> Iterator[tuple[int, str]]:
    """Yield numbered atlas data lines after metadata has been skipped."""

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        if should_skip_line(line):
            continue
        yield line_number, line


def parse_atlas_file(path: str | Path) -> ParsedAtlas:
    """Parse an Astrolog atlas source file into canonical records.

    The parser skips blank lines plus metadata lines beginning with ``;``, ``@``,
    and ``-YY`` while still preserving comment metadata and declared record count.
    """

    source_path = Path(path)
    source_tag = ""
    declared_record_count: int | None = None
    comment_lines: list[str] = []
    records: list[AtlasRecord] = []
    previous_timezone: str | None = None

    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("@"):
                if not source_tag:
                    source_tag = stripped.split(None, 1)[0]
                continue

            if stripped.startswith(";"):
                comment_lines.append(stripped[1:].strip())
                continue

            count = parse_declared_record_count(line)
            if count is not None:
                if declared_record_count is not None:
                    raise AtlasParseError(f"Duplicate record count line: {stripped!r}")
                declared_record_count = count
                continue

            record = parse_record_line(
                line=line,
                line_number=line_number,
                record_id=len(records) + 1,
                previous_timezone=previous_timezone,
            )
            records.append(record)
            previous_timezone = record.timezone

    if not source_tag:
        source_tag = "@UNKNOWN"
    if declared_record_count is None:
        declared_record_count = len(records)

    if declared_record_count != len(records):
        raise AtlasParseError(
            "Declared record count does not match parsed records: "
            f"{declared_record_count} != {len(records)}"
        )

    metadata = AtlasMetadata(
        source_tag=source_tag,
        declared_record_count=declared_record_count,
        comment_lines=tuple(comment_lines),
    )
    return ParsedAtlas(metadata=metadata, records=tuple(records))


def parse_record_line(
    *,
    line: str,
    line_number: int,
    record_id: int,
    previous_timezone: str | None,
) -> AtlasRecord:
    """Parse a single tab-delimited atlas record line."""

    parts = line.split("\t")
    if len(parts) not in {4, 5}:
        raise AtlasParseError(
            f"Unexpected field count at line {line_number}: got {len(parts)} fields"
        )

    timezone = parts[4] if len(parts) == 5 else previous_timezone
    if not timezone:
        raise AtlasParseError(
            f"Missing timezone at line {line_number} with no prior timezone to inherit"
        )

    try:
        longitude_astrolog = float(parts[0])
        latitude = float(parts[1])
    except ValueError as exc:
        raise AtlasParseError(f"Invalid coordinates at line {line_number}: {line!r}") from exc

    region_code = parts[2]
    city = parts[3]
    return AtlasRecord(
        record_id=record_id,
        city=city,
        city_norm=normalize_city_name(city),
        region_code=region_code,
        latitude=latitude,
        longitude_astrolog=longitude_astrolog,
        longitude_standard=astrolog_to_standard_longitude(longitude_astrolog),
        timezone=timezone,
    )


def iter_records(path: str | Path) -> Iterable[AtlasRecord]:
    """Yield canonical atlas records from a source file."""

    return parse_atlas_file(path).records
