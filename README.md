# Multidimensional Chart Calculator

**Python-based astrological and Human Design calculation engine**

An in-development calculation system combining astronomical positioning, astrological geometry, Human Design subdivisions, and offline geographic lookup.

The project uses a modular Python architecture with a FastAPI interface, Swiss Ephemeris calculations, and a locally compiled SQLite geographic database.

## Project Overview

The Multidimensional Chart Calculator is designed to provide a foundation for calculating and integrating multiple chart-based systems.

The current implementation supports astronomical and astrological calculations, birth-location resolution, time normalization, and selected Human Design calculations.

The project is under active development. Its existing API exposes geographic and astrological functionality; Human Design calculations are currently available through Python modules rather than dedicated API endpoints.

## Implemented Features

### Geographic Lookup and Time Normalization

- Offline city lookup using a locally compiled SQLite database.
- Exact-name and prefix-based geographic searches.
- Geographic coordinate and timezone resolution.
- Local birth-date and birth-time conversion to UTC.
- Error handling for missing or ambiguous city matches.

### Astronomy and Astrology

- Planetary position calculations using Swiss Ephemeris.
- Zodiac longitude conversion into sign, degree, and minute.
- Ascendant, Midheaven, and Vertex calculations.
- Astrological house cusps and planetary house placement.
- Koch house system with Placidus fallback handling.

### Human Design

Python modules provide:

- Gate and line boundary lookup.
- Color subdivision calculations.
- Tone subdivision calculations.
- Base subdivision calculations.
- Reference-data loading from ODS spreadsheets.

Human Design functionality is not yet exposed through dedicated FastAPI endpoints.

The variables module is currently a placeholder.

## Technology Stack

- Python 3.12+
- FastAPI
- Uvicorn
- Swiss Ephemeris (`pyswisseph`)
- SQLite
- pytest
- OpenDocument Spreadsheet (ODS) parsing

## Installation

Clone the repository and navigate to its root directory.

Install the project and its development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

The application requires a locally compiled Atlas database before the FastAPI service can start.

## Offline Atlas Database Setup

The Atlas source data is not included in this repository.

The application uses the Astrolog Atlas format. Obtain a compatible `atlas.as` source file from the [Astrolog project](https://github.com/CruiserOne/Astrolog).

Place the file at `data/atlas.as`, or specify its location explicitly.

Build the local SQLite database:

```powershell
python -m src.build_atlas_db --source data/atlas.as
```

On Windows, the default output location is:

```text
%LOCALAPPDATA%\atlas-offline-lookup\atlas.sqlite3
```

To specify another database location:

```powershell
python -m src.build_atlas_db --source data/atlas.as --output C:\path\to\atlas.sqlite3
```

If necessary, set `ATLAS_DB_PATH` to the compiled database location before starting the API.

After compilation, geographic lookups operate locally without a network connection.

## Run the API

From the repository root:

```powershell
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

FastAPI's interactive API documentation is available at:

`http://127.0.0.1:8000/docs`

### Available Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/lookup/exact` | Exact city lookup |
| GET | `/lookup/prefix` | Prefix-based city search |
| POST | `/normalize-birthtime` | Local birth-time conversion to UTC |
| POST | `/calculate-positions` | Planetary positions and astrological geometry |

### Example: Calculate Positions

```powershell
$body = @{
    utc_datetime = "2024-01-15T18:45:00+00:00"
    latitude = 40.7484
    longitude = -73.9857
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/calculate-positions" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

The calculation response includes zodiac positions, house placements, house cusps, and chart angles.

## Automated Testing

Run the test suite:

```powershell
python -m pytest -q
```

**Latest local validation:** 51 tests passed on November 14, 2026.

Tests cover Atlas parsing and indexing, geographic lookup, birth-time normalization, planetary calculations, astrological geometry, and selected Human Design subdivisions.

The tests use generated fixtures and do not require the original Atlas dataset.

## Current Development Status

Implemented:

- Offline geographic lookup infrastructure.
- Local birth-time normalization.
- Astrological position and geometry calculations.
- Human Design gate, line, color, tone, and base calculation modules.
- Automated Python test suite.

Not yet implemented or fully integrated:

- Dedicated Human Design API endpoints.
- Human Design variable calculations.
- Unified multidimensional chart output.
- Graphical chart visualization.
- A deployed public application.

## Third-Party Data and Attribution

**Astrolog:** The Atlas source format and original geographic dataset are associated with Walter Pullen's [Astrolog project](https://github.com/CruiserOne/Astrolog). Astrolog's licensing terms apply to its own distributed materials.

**GeoNames:** The underlying geographic data is attributed by Astrolog to [GeoNames](https://www.geonames.org/), under Creative Commons Attribution 4.0.

**Swiss Ephemeris:** Astronomical calculations use the Swiss Ephemeris Python package. Swiss Ephemeris has its own licensing requirements, which should be reviewed before redistribution or commercial deployment.

The original Astrolog Atlas source and derived SQLite database are not distributed in this repository.

## Project Scope

This repository documents the technical foundation of a multidimensional calculation system. It is a development-stage software project, not a completed commercial charting application.

## License and Acknowledgments

Copyright © 2026. Licensed under the GNU Affero General Public License, version 3 (AGPLv3).

This project uses Swiss Ephemeris through the `pyswisseph` Python package. Third-party software and data remain subject to their respective licenses and attribution requirements.

### A Personal Request

This project began as a labor of love and a personal exploration of multidimensional calculation systems.

If you find the code useful, adapt it, or build something new with it, I'd love to hear about your project and what inspired you.

Sharing your work or getting in touch is entirely voluntary and is not a condition of the license.

I hope this project contributes to someone else's learning, experimentation, or creative development.