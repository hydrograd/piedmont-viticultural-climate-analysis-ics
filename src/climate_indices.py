"""Annual climate indices from daily temperature and precipitation.

Given daily regional-mean series of maximum temperature and precipitation, this
computes the per-year indicators used downstream by the compound classifier:

  Seasonal
    - summer_heatwave_days : JJA days with mean Tmax above HEAT_TMAX_THRESHOLD_C
    - summer_mean_tmax_c    : JJA mean of daily-max temperature
    - growing_precip_mm     : Apr to Sep total precipitation

  Monthly (used to distinguish concurrent from sequential events)
    - tmax_m04..09  : mean daily-max temperature per growing-season month
    - precip_m04..09: total precipitation per growing-season month

``compute_indices`` is source-agnostic: it takes two daily pandas Series and is
called by both ingest paths (Open-Meteo and CDS/ERA5).

``main`` runs the CDS/ERA5 NetCDF path: it reads the files produced by
``climate_ingest``, reduces them to daily regional-mean series, and writes
``piedmont_climate_indices.csv``. The Open-Meteo path in
``climate_ingest_openmeteo`` calls ``compute_indices`` directly.

    python -m src.climate_indices
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

import config
from src import climate_ingest


# --- NetCDF coordinate helpers (names vary between ERA5 products) -----------
def _time_name(ds: xr.Dataset) -> str:
    for c in ("valid_time", "time", "forecast_reference_time"):
        if c in ds.coords or c in ds.dims:
            return c
    raise KeyError(f"No time coordinate found in {list(ds.coords)}")


def _spatial_dims(da: xr.DataArray, tname: str) -> list[str]:
    """The non-time dims to average over (lat/lon or y/x)."""
    return [d for d in da.dims if d != tname]


def _main_var(ds: xr.Dataset) -> str:
    names = list(ds.data_vars)
    if not names:
        raise ValueError("No data variables in dataset")
    return names[0]


def _daily_series(path, to_celsius=False, precip_mm=False) -> pd.Series:
    """Load a NetCDF file, average over the box, and return a daily series."""
    ds = xr.open_dataset(path)
    vname = _main_var(ds)
    tname = _time_name(ds)
    da = ds[vname].mean(dim=_spatial_dims(ds[vname], tname))
    s = pd.Series(da.values, index=pd.to_datetime(ds[tname].values)).sort_index()
    if to_celsius:
        s = s - 273.15
    if precip_mm:
        # daily_mean of hourly total_precipitation (m) -> daily total in mm
        s = s * 24.0 * 1000.0
    return s


def compute_indices(tmax: pd.Series, precip: pd.Series) -> pd.DataFrame:
    """Reduce daily Tmax (Celsius) and precipitation (mm) to per-year indices."""
    rows = []
    for year in sorted(set(tmax.index.year)):
        ty = tmax[tmax.index.year == year]
        py = precip[precip.index.year == year]
        if ty.empty or py.empty:
            continue
        rec: dict = {"year": int(year)}

        summer = ty[ty.index.month.isin(config.SUMMER_MONTHS)]
        rec["summer_heatwave_days"] = int((summer > config.HEAT_TMAX_THRESHOLD_C).sum())
        rec["summer_mean_tmax_c"] = float(summer.mean())

        gs_precip = py[py.index.month.isin(config.GROWING_SEASON_MONTHS)]
        rec["growing_precip_mm"] = float(gs_precip.sum())

        for m in config.GROWING_SEASON_MONTHS:
            tm = ty[ty.index.month == m]
            pm = py[py.index.month == m]
            rec[f"tmax_m{m:02d}"] = float(tm.mean()) if len(tm) else np.nan
            rec[f"precip_m{m:02d}"] = float(pm.sum()) if len(pm) else np.nan
        rows.append(rec)
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def main() -> pd.DataFrame:
    tpath, ppath = climate_ingest.tmax_path(), climate_ingest.precip_path()
    if not (tpath.exists() and ppath.exists()):
        raise SystemExit(
            f"Missing ERA5 files in {climate_ingest.ERA5_DIR}. Run "
            "`python -m src.climate_ingest` first, or use the Open-Meteo path "
            "(`python -m src.climate_ingest_openmeteo`)."
        )
    tmax = _daily_series(tpath, to_celsius=True)
    precip = _daily_series(ppath, precip_mm=True)
    df = compute_indices(tmax, precip)
    df.to_csv(config.CLIMATE_CSV, index=False)
    print(f"Climate indices -> {config.CLIMATE_CSV} ({len(df)} years)")
    print(df[["year", "summer_heatwave_days", "summer_mean_tmax_c", "growing_precip_mm"]]
          .to_string(index=False))
    return df


if __name__ == "__main__":
    main()
