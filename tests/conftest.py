"""Shared fixtures and path setup for the test suite.

The project modules import ``config`` from the repository root, so the root has
to be importable when pytest is run from anywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402  (import after sys.path is set)

GS_MONTHS = config.GROWING_SEASON_MONTHS


@pytest.fixture
def shifted_istat_csv(tmp_path: Path) -> Path:
    """A miniature ISTAT extract carrying the one-column header shift.

    The real source file labels its columns one position to the left of the
    values they describe: the column headed ``Year`` holds the crop name, and
    ``Observation`` holds the production figure. Two provinces are included plus
    one row from outside Piedmont, so filtering can be checked as well.
    """
    rows = [
        # Region_code, Region_name, Year(=crop), Crop(=year), Observation(=production),
        # Amount(=area_ha), Area(=yield_per_ha), Yield(all-NaN in the source)
        ("ITC16", "Cuneo",      "WINEES", 2020, 1000.0, 100.0, 10.0, ""),
        ("ITC16", "Cuneo",      "WINEES", 2021,  900.0,  90.0, 10.0, ""),
        ("ITC17", "Asti",       "WINEES", 2020,  400.0,  20.0, 20.0, ""),
        ("ITC17", "Asti",       "WINEES", 2021,  600.0,  30.0, 20.0, ""),
        ("ITF33", "Napoli",     "WINEES", 2020,  500.0,  50.0, 10.0, ""),
    ]
    header = ["Region_code", "Region_name", "Year", "Crop",
              "Observation", "Amount", "Area", "Yield"]
    path = tmp_path / "istat_shifted.csv"
    pd.DataFrame(rows, columns=header).to_csv(path, index=False)
    return path


def make_daily(year: int, tmax_by_month: dict, precip_by_month: dict) -> tuple:
    """Build daily Tmax and precipitation series for one year.

    ``tmax_by_month`` and ``precip_by_month`` map month number to the constant
    value every day of that month takes. Months left out default to a mild 15 C
    and 3 mm, which fall in no extreme category.
    """
    idx = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    tmax = pd.Series(
        [tmax_by_month.get(ts.month, 15.0) for ts in idx], index=idx, dtype=float)
    precip = pd.Series(
        [precip_by_month.get(ts.month, 3.0) for ts in idx], index=idx, dtype=float)
    return tmax, precip


def make_climate_frame(heatwave_days, growing_precip, monthly_tmax=None,
                       monthly_precip=None, start_year: int = 2006) -> pd.DataFrame:
    """Assemble the annual climate-index frame that ``classify_years`` consumes.

    ``heatwave_days`` and ``growing_precip`` are per-year sequences. The monthly
    columns default to flat values, which makes every month equally extreme and
    so exercises only the year-level severity rule.
    """
    n = len(heatwave_days)
    years = list(range(start_year, start_year + n))
    data = {
        "year": years,
        "summer_heatwave_days": list(heatwave_days),
        "summer_mean_tmax_c": [25.0] * n,
        "growing_precip_mm": list(growing_precip),
    }
    for m in GS_MONTHS:
        key = f"tmax_m{m:02d}"
        data[key] = list(monthly_tmax[m]) if monthly_tmax and m in monthly_tmax \
            else [20.0 + i * 0.0 for i in range(n)]
        key = f"precip_m{m:02d}"
        data[key] = list(monthly_precip[m]) if monthly_precip and m in monthly_precip \
            else [50.0] * n
    return pd.DataFrame(data)


def make_production_frame(years, yields, area=100.0) -> pd.DataFrame:
    """A regional production frame of the shape ``detrend_yield`` expects."""
    return pd.DataFrame({
        "region": [config.REGION_NAME] * len(years),
        "year": list(years),
        "production": [y * area for y in yields],
        "area_ha": [area] * len(years),
        "yield_per_ha": list(yields),
        "n_provinces": [7] * len(years),
    })


@pytest.fixture
def daily_builder():
    return make_daily


@pytest.fixture
def climate_frame_builder():
    return make_climate_frame


@pytest.fixture
def production_frame_builder():
    return make_production_frame
