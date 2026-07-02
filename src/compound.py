"""Compound-event classification and the headline production-risk comparison.

Joins the annual climate indices to the production series and labels each year:

    normal | heat_only | drought_only | concurrent | sequential

The definition is two-level:

  Year-level severity decides whether a year is heat- and/or drought-stressed:
    - heat year   : summer heatwave-day count in the warmest fraction of years
    - drought year: growing-season precipitation in the driest fraction of years
    (the fraction is config.COMPOUND_SEVERITY_PCTL)

  For years that are both, month-level timing splits them:
    - concurrent: at least one growing-season month is itself both hot and dry
                  (the stresses overlap in time)
    - sequential: the heat and drought fall in different months (in sequence,
                  with no single overlapping month)

Year-level severity is used rather than "any hot month exists" because over an
~18-year record almost every year has some hot month and some dry month; a purely
monthly rule would label nearly everything compound and leave no comparison
group. See ANALYSIS.md for the rationale and the threshold sensitivity.

The headline compares mean yield (and detrended yield anomaly) in compound years
against normal years.

    python -m src.compound
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config


def _extreme_flags(values: pd.Series, warm_side: bool, pctl: float) -> pd.Series:
    """True where a value falls in the extreme ``pctl`` fraction of the record.

    warm_side=True flags the top fraction (hot); False flags the bottom (dry).
    """
    if warm_side:
        return values >= values.quantile(1 - pctl)
    return values <= values.quantile(pctl)


def classify_years(climate: pd.DataFrame) -> pd.DataFrame:
    """Add heat/drought flags and a compound category to each year."""
    df = climate.copy()
    months = config.GROWING_SEASON_MONTHS
    pctl = config.COMPOUND_SEVERITY_PCTL

    # Year-level severity: is this year among the hottest / driest of the record?
    df["heat_flag"] = _extreme_flags(df["summer_heatwave_days"], warm_side=True, pctl=pctl).values
    df["drought_flag"] = _extreme_flags(df["growing_precip_mm"], warm_side=False, pctl=pctl).values

    # Month-level flags, used only to split concurrent vs sequential. A fixed
    # tercile is fine here since it just tests co-occurrence within a year.
    hot = pd.DataFrame({m: _extreme_flags(df[f"tmax_m{m:02d}"], True, 1 / 3) for m in months},
                       index=df.index)
    dry = pd.DataFrame({m: _extreme_flags(df[f"precip_m{m:02d}"], False, 1 / 3) for m in months},
                       index=df.index)

    categories = []
    for i in df.index:
        is_heat, is_dry = bool(df.loc[i, "heat_flag"]), bool(df.loc[i, "drought_flag"])
        if is_heat and is_dry:
            hot_months = {m for m in months if bool(hot.loc[i, m])}
            dry_months = {m for m in months if bool(dry.loc[i, m])}
            # A month that is both hot and dry means the stresses overlap.
            cat = "concurrent" if (hot_months & dry_months) else "sequential"
        elif is_heat:
            cat = "heat_only"
        elif is_dry:
            cat = "drought_only"
        else:
            cat = "normal"
        categories.append(cat)

    df["category"] = categories
    df["is_compound"] = df["category"].isin(["concurrent", "sequential"])
    return df


def detrend_yield(prod: pd.DataFrame) -> pd.DataFrame:
    """Add a detrended yield anomaly (percent deviation from the linear trend).

    Removing the trend strips out the long-run decline in vineyard area so the
    residual reflects year-to-year climate sensitivity rather than structural or
    economic change.
    """
    df = prod.copy()
    x = df["year"].to_numpy(dtype=float)
    y = df["yield_per_ha"].to_numpy(dtype=float)
    trend = np.polyval(np.polyfit(x, y, 1), x)
    df["yield_trend"] = trend
    df["yield_anom_pct"] = (y - trend) / trend * 100.0
    return df


def build(production_csv=config.PRODUCTION_CSV, climate_csv=config.CLIMATE_CSV) -> pd.DataFrame:
    """Join detrended production to classified climate over the analysis window."""
    prod = detrend_yield(pd.read_csv(production_csv))
    climate = classify_years(pd.read_csv(climate_csv))
    merged = prod.merge(climate, on="year", how="inner")
    merged = merged[(merged["year"] >= config.ANALYSIS_START_YEAR)
                    & (merged["year"] <= config.ANALYSIS_END_YEAR)]
    return merged.reset_index(drop=True)


def headline(merged: pd.DataFrame) -> dict:
    """Compound vs normal comparison, plus the counts used by the dashboard."""
    compound = merged[merged["is_compound"]]
    normal = merged[merged["category"] == "normal"]

    out = {
        "n_total": len(merged),
        "n_compound": len(compound),
        "n_normal": len(normal),
        "mean_yield_compound": float(compound["yield_per_ha"].mean()) if len(compound) else np.nan,
        "mean_yield_normal": float(normal["yield_per_ha"].mean()) if len(normal) else np.nan,
        "compound_years": compound["year"].tolist(),
    }
    if len(compound) and len(normal):
        out["pct_difference"] = ((out["mean_yield_compound"] - out["mean_yield_normal"])
                                 / out["mean_yield_normal"] * 100.0)
    else:
        out["pct_difference"] = np.nan
    return out


def main() -> pd.DataFrame:
    merged = build()
    merged.to_csv(config.COMPOUND_CSV, index=False)
    h = headline(merged)

    print(f"Compound analysis -> {config.COMPOUND_CSV}")
    print(merged[["year", "yield_per_ha", "yield_anom_pct", "summer_heatwave_days",
                  "growing_precip_mm", "category"]].to_string(index=False))
    print(f"\nCompound years ({h['n_compound']}): {h['compound_years']}")
    if not np.isnan(h["pct_difference"]):
        direction = "lower" if h["pct_difference"] < 0 else "higher"
        print(f"Mean yield in compound years was {abs(h['pct_difference']):.1f}% {direction} "
              f"than in normal years ({h['mean_yield_compound']:.1f} vs "
              f"{h['mean_yield_normal']:.1f} q/ha).")
    else:
        print("Not enough compound or normal years to compute the comparison.")
    return merged


if __name__ == "__main__":
    main()
