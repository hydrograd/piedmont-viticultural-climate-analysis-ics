"""Grape-production pipeline.

Loads the ISTAT wine-grape extract, corrects a mislabelled header in the source
file, and builds two annual series for Piedmont: a regional total and a
per-province breakdown (the latter feeds the dashboard choropleth).

Run to (re)generate the processed CSVs:

    python -m src.production
"""
from __future__ import annotations

import pandas as pd

import config


# The source CSV ships with a header that is shifted one column to the left of
# the values it labels. The mapping below is verified against the raw data (e.g.
# the column labelled "Year" actually holds the crop name, and "Observation"
# holds the production figure). We read the columns positionally and rename them
# to their true meaning; the trailing "Yield" column is all-NaN and dropped.
_RENAME = {
    "Region_code": "region_code",
    "Region_name": "region_name",
    "Year": "crop",          # actually the crop type (all "WINEES")
    "Crop": "year",          # actually the year
    "Observation": "production",
    "Amount": "area_ha",
    "Area": "yield_per_ha",
}


def load_raw_istat(path=config.ISTAT_CSV) -> pd.DataFrame:
    """Load the ISTAT CSV and rename the shifted columns to their true meaning."""
    df = pd.read_csv(path).rename(columns=_RENAME)
    df = df[["region_code", "region_name", "crop", "year",
             "production", "area_ha", "yield_per_ha"]]
    for col in ("year", "production", "area_ha", "yield_per_ha"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def build_piedmont_series(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the Piedmont provinces into one annual regional series.

    Production and area are summed across provinces. Yield is recomputed from the
    regional totals (an area-weighted yield), not averaged from the per-province
    ratios, which would double-count small provinces.
    """
    pied = df[df["region_code"].isin(config.PIEDMONT_PROVINCE_CODES)].copy()
    if pied.empty:
        raise ValueError("No Piedmont province rows found; check PIEDMONT_PROVINCE_CODES.")

    grouped = (
        pied.groupby("year")
        .agg(production=("production", "sum"),
             area_ha=("area_ha", "sum"),
             n_provinces=("region_code", "nunique"))
        .reset_index()
        .sort_values("year")
    )
    grouped["yield_per_ha"] = grouped["production"] / grouped["area_ha"]
    grouped["region"] = config.REGION_NAME
    return grouped[["region", "year", "production", "area_ha", "yield_per_ha", "n_provinces"]]


def build_province_series(df: pd.DataFrame) -> pd.DataFrame:
    """Per-province annual series for the dashboard choropleth.

    Keeps the NUTS-3 ``region_code`` so it joins to the province GeoJSON on
    ``NUTS_ID``.
    """
    pied = df[df["region_code"].isin(config.PIEDMONT_PROVINCE_CODES)].copy()
    out = (pied.groupby(["region_code", "region_name", "year"])
           .agg(production=("production", "sum"), area_ha=("area_ha", "sum"))
           .reset_index())
    out["yield_per_ha"] = out["production"] / out["area_ha"]
    return out.sort_values(["region_code", "year"])


def main() -> pd.DataFrame:
    raw = load_raw_istat()

    series = build_piedmont_series(raw)
    series.to_csv(config.PRODUCTION_CSV, index=False)

    provinces = build_province_series(raw)
    provinces.to_csv(config.PRODUCTION_BY_PROVINCE_CSV, index=False)

    print(f"Regional series  -> {config.PRODUCTION_CSV}")
    print(f"Province series  -> {config.PRODUCTION_BY_PROVINCE_CSV} "
          f"({provinces['region_code'].nunique()} provinces)")
    print(f"Years {int(series['year'].min())} to {int(series['year'].max())} "
          f"({len(series)} years)")
    print(series.to_string(index=False))
    return series


if __name__ == "__main__":
    main()
