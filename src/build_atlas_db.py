"""CLI entry point for compiling an Astrolog atlas into SQLite."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .atlas_index import build_sqlite_database
from .atlas_parser import parse_atlas_file


def default_database_path() -> Path:
    """Return the default local path for the compiled SQLite artifact."""

    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return local_appdata / "atlas-offline-lookup" / "atlas.sqlite3"


def build_database(source_path: str | Path, database_path: str | Path) -> None:
    """Parse an atlas file and write the compiled SQLite artifact."""

    parsed = parse_atlas_file(source_path)
    build_sqlite_database(
        database_path=database_path,
        metadata=parsed.metadata,
        records=parsed.records,
    )


def main() -> None:
    """Parse command line arguments and build the atlas database."""

    parser = argparse.ArgumentParser(
        description="Compile an Astrolog atlas file into a SQLite lookup database."
    )
    parser.add_argument(
        "--source",
        default="data/atlas.as",
        help="Path to the source atlas.as file.",
    )
    parser.add_argument(
        "--output",
        default=str(default_database_path()),
        help="Path to the compiled SQLite database.",
    )
    args = parser.parse_args()
    build_database(source_path=args.source, database_path=args.output)


if __name__ == "__main__":
    main()
