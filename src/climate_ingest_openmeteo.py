"""Climate ingest via the Open-Meteo historical API (default path).

Open-Meteo's historical archive serves ERA5, so this is the same underlying
reanalysis as the CDS path, but delivered through a free, no-key HTTP API with no
request queue.

Method:
  1. Sample the wine districts in config.WINE_DISTRICTS (grape-growing areas, not
     province centroids, which fall in the Alps and misrepresent the vineyards).
  2. For each point, fetch daily maximum 2 m temperature (Celsius) and daily
     precipitation (mm) from the pure ERA5 model.
  3. Average across points to a Piedmont wine-region daily series.
  4. Pass the series to climate_indices.compute_indices and write
     piedmont_climate_indices.csv.

Two data-quality notes handled below:
  - The default and ERA5-Land models have whole-year gaps over Piedmont
    (2006, 2008, 2011), so we request the pure ERA5 model explicitly.
  - ERA5 precipitation is missing 2017 in Open-Meteo; that gap is back-filled
    from the best_match model.

Raw responses are cached per district under data/raw/openmeteo/, so re-runs are
instant and resilient to rate limits.

    python -m src.climate_ingest_openmeteo
"""
from __future__ import annotations

import time

import pandas as pd
import requests

import config
from src import climate_indices

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
RAW_DIR = config.DATA_RAW / "openmeteo"


def _get(params: dict, retries: int = 5) -> dict:
    """GET the daily block from Open-Meteo, backing off on rate limits (429)."""
    for attempt in range(retries):
        r = requests.get(ARCHIVE_URL, params=params, timeout=90)
        if r.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"    rate-limited (429); waiting {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()["daily"]
    raise RuntimeError(f"Open-Meteo still rate-limiting after {retries} retries")


def _fetch_point(lat: float, lon: float) -> pd.DataFrame:
    """Daily Tmax (Celsius) and precipitation (mm) for one point."""
    base = {
        "latitude": lat, "longitude": lon,
        "start_date": f"{config.CLIMATE_START_YEAR}-01-01",
        "end_date": f"{config.CLIMATE_END_YEAR}-12-31",
        "daily": "temperature_2m_max,precipitation_sum",
        "timezone": "UTC",
    }
    era5 = _get({**base, "models": "era5"})
    idx = pd.to_datetime(era5["time"])
    tmax = pd.Series(era5["temperature_2m_max"], index=idx)
    precip = pd.Series(era5["precipitation_sum"], index=idx)

    # Back-fill the ERA5 precipitation gap (2017) from best_match.
    if precip.isna().any():
        time.sleep(2)
        bm = _get(base)
        bm_precip = pd.Series(bm["precipitation_sum"], index=pd.to_datetime(bm["time"]))
        precip = precip.combine_first(bm_precip)
    return pd.DataFrame({"tmax": tmax, "precip": precip})


def build_series() -> tuple[pd.Series, pd.Series]:
    """Return daily (Tmax in Celsius, precip in mm) averaged over the districts.

    Districts already cached under data/raw/openmeteo/ are loaded from disk, so a
    re-run only fetches what is missing.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    tmax_cols, precip_cols = {}, {}
    for name, lat, lon in config.WINE_DISTRICTS:
        cache = RAW_DIR / f"{name.replace('/', '-').replace(' ', '_')}.csv"
        if cache.exists():
            print(f"  [cache] {name}")
            df = pd.read_csv(cache, parse_dates=["date"]).set_index("date")
        else:
            print(f"  [fetch] {name} ({lat}, {lon})")
            df = _fetch_point(lat, lon)
            df.to_csv(cache, index_label="date")
            time.sleep(2)  # courtesy delay for the free API
        tmax_cols[name] = df["tmax"]
        precip_cols[name] = df["precip"]
    tmax = pd.DataFrame(tmax_cols).mean(axis=1)
    precip = pd.DataFrame(precip_cols).mean(axis=1)
    return tmax.sort_index(), precip.sort_index()


def main() -> pd.DataFrame:
    print(f"Open-Meteo ingest for {config.REGION_NAME}, "
          f"{config.CLIMATE_START_YEAR} to {config.CLIMATE_END_YEAR}")
    tmax, precip = build_series()
    df = climate_indices.compute_indices(tmax, precip)
    df.to_csv(config.CLIMATE_CSV, index=False)
    print(f"\nClimate indices -> {config.CLIMATE_CSV} ({len(df)} years)")
    print(df[["year", "summer_heatwave_days", "summer_mean_tmax_c", "growing_precip_mm"]]
          .to_string(index=False))
    return df


if __name__ == "__main__":
    main()
