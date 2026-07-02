"""Climate ingest via the Copernicus Climate Data Store (ERA5).

This is the "official source" ingest path. It downloads daily maximum temperature
and daily precipitation for the Piedmont bounding box from the CDS "ERA5 daily
statistics" derived dataset, which aggregates hourly to daily server-side and
supports area subsetting, so each file is small.

The default pipeline uses ``climate_ingest_openmeteo`` instead, because the CDS
request queue can be slow (minutes to tens of minutes per request). This module
is kept for cross-checking against Copernicus directly.

Requirements: a free CDS account, ``pip install cdsapi``, and ``~/.cdsapirc``
holding the API URL and key (see README, "CDS setup").

Output: two NetCDF files in ``data/raw/era5/`` covering the configured years,
ready for ``climate_indices.main``.

    python -m src.climate_ingest
"""
from __future__ import annotations

import config

ERA5_DIR = config.DATA_RAW / "era5"
DAILY_DATASET = "derived-era5-single-levels-daily-statistics"

_ALL_MONTHS = [f"{m:02d}" for m in range(1, 13)]
_ALL_DAYS = [f"{d:02d}" for d in range(1, 32)]


def _years() -> list[str]:
    return [str(y) for y in range(config.CLIMATE_START_YEAR, config.CLIMATE_END_YEAR + 1)]


def tmax_path():
    return ERA5_DIR / f"tmax_{config.CLIMATE_START_YEAR}_{config.CLIMATE_END_YEAR}.nc"


def precip_path():
    return ERA5_DIR / f"precip_{config.CLIMATE_START_YEAR}_{config.CLIMATE_END_YEAR}.nc"


def _request(variable: str, statistic: str, years: list[str]) -> dict:
    return {
        "product_type": "reanalysis",
        "variable": [variable],
        "year": years,
        "month": _ALL_MONTHS,
        "day": _ALL_DAYS,
        "daily_statistic": statistic,
        "time_zone": "utc+00:00",
        "frequency": "1_hourly",
        "area": config.PIEDMONT_BBOX,  # [North, West, South, East]
    }


def _too_large(err: Exception) -> bool:
    msg = str(err).lower()
    return "too large" in msg or "cost limit" in msg or "reduce your selection" in msg


def _download_chunked(client, variable, statistic, years, tmp_dir) -> list:
    """Download ``years`` in one request.

    A single request for the full range is fastest, but CDS rejects requests that
    exceed its per-request cost limit. When that happens we split the year range
    in half and retry each half, so the code self-tunes to whatever CDS allows.
    Completed chunks are cached, so a re-run resumes rather than restarting.
    """
    tag = f"{years[0]}_{years[-1]}"
    out = tmp_dir / f"_chunk_{variable[:4]}_{tag}.nc"
    if out.exists():
        print(f"    [skip] chunk {tag} present")
        return [out]
    try:
        print(f"    [get ] {variable} {tag} ({len(years)} yr)")
        client.retrieve(DAILY_DATASET, _request(variable, statistic, years)).download(str(out))
        return [out]
    except Exception as e:  # noqa: BLE001 - only the size error is special-cased
        if _too_large(e) and len(years) > 1:
            mid = len(years) // 2
            print(f"    [split] {tag} exceeds the CDS cost limit; splitting")
            return (_download_chunked(client, variable, statistic, years[:mid], tmp_dir)
                    + _download_chunked(client, variable, statistic, years[mid:], tmp_dir))
        raise


def _concat(chunk_files, target) -> None:
    import xarray as xr
    ds = xr.open_mfdataset([str(f) for f in sorted(chunk_files)], combine="by_coords")
    ds.to_netcdf(str(target))
    ds.close()


def main() -> None:
    import cdsapi  # imported here so the rest of the repo runs without cdsapi

    ERA5_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = ERA5_DIR / "_chunks"
    tmp_dir.mkdir(exist_ok=True)
    client = cdsapi.Client()

    jobs = [
        ("2m_temperature", "daily_maximum", tmax_path()),
        ("total_precipitation", "daily_mean", precip_path()),
    ]
    yrs = _years()
    print(f"Downloading ERA5 daily Tmax and precip for {config.REGION_NAME}, "
          f"years {yrs[0]} to {yrs[-1]} (adaptive chunking).")
    for variable, statistic, target in jobs:
        if target.exists():
            print(f"  [skip] {target.name} already present")
            continue
        print(f"  {target.name}:")
        chunks = _download_chunked(client, variable, statistic, yrs, tmp_dir)
        _concat(chunks, target)
        print(f"  [done] {target.name} from {len(chunks)} chunk(s)")
    print(f"Done. Files in {ERA5_DIR}")


if __name__ == "__main__":
    main()
