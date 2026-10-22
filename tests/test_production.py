"""Tests for the grape-production pipeline.

The header-shift correction is the single highest-risk step in the project: the
source CSV labels its columns one position to the left of the values they
describe, so an uncorrected read silently puts the crop name in ``year`` and the
area in ``production``. Every downstream figure would be wrong and nothing would
raise. The first test here is the regression guard for that.
"""
from __future__ import annotations

import pandas as pd
import pytest

import config
from src import production


class TestLoadRawIstat:
    def test_header_shift_is_corrected(self, shifted_istat_csv):
        """``production`` must hold production, not area, and ``year`` a year."""
        df = production.load_raw_istat(shifted_istat_csv)

        cuneo_2020 = df[(df["region_code"] == "ITC16") & (df["year"] == 2020)].iloc[0]
        assert cuneo_2020["production"] == pytest.approx(1000.0)
        assert cuneo_2020["area_ha"] == pytest.approx(100.0)
        assert cuneo_2020["crop"] == "WINEES"

    def test_year_is_numeric_not_the_crop_name(self, shifted_istat_csv):
        df = production.load_raw_istat(shifted_istat_csv)
        assert pd.api.types.is_numeric_dtype(df["year"])
        assert set(df["year"].dropna()) == {2020, 2021}

    def test_production_exceeds_area_in_every_row(self, shifted_istat_csv):
        """A cheap invariant that catches the two columns being swapped.

        Production is measured in quintals and area in hectares, so for wine
        grapes production is always the larger number. If the shift correction
        were dropped or reversed this would fail immediately.
        """
        df = production.load_raw_istat(shifted_istat_csv)
        assert (df["production"] > df["area_ha"]).all()

    def test_expected_columns_present_and_ordered(self, shifted_istat_csv):
        df = production.load_raw_istat(shifted_istat_csv)
        assert list(df.columns) == ["region_code", "region_name", "crop", "year",
                                    "production", "area_ha", "yield_per_ha"]


class TestBuildPiedmontSeries:
    def test_non_piedmont_provinces_are_excluded(self, shifted_istat_csv):
        """The Napoli row in the fixture must not reach the regional total."""
        raw = production.load_raw_istat(shifted_istat_csv)
        series = production.build_piedmont_series(raw)

        total_2020 = series[series["year"] == 2020]["production"].iloc[0]
        # Cuneo 1000 + Asti 400, with Napoli's 500 left out.
        assert total_2020 == pytest.approx(1400.0)

    def test_yield_is_area_weighted_not_a_mean_of_ratios(self, shifted_istat_csv):
        """Regional yield is recomputed from the totals.

        In 2020 Cuneo yields 10 q/ha over 100 ha and Asti 20 q/ha over 20 ha.
        The mean of the two ratios is 15, which over-weights the small province.
        The correct area-weighted figure is 1400/120 = 11.67.
        """
        raw = production.load_raw_istat(shifted_istat_csv)
        series = production.build_piedmont_series(raw)

        yield_2020 = series[series["year"] == 2020]["yield_per_ha"].iloc[0]
        assert yield_2020 == pytest.approx(1400.0 / 120.0)
        assert yield_2020 != pytest.approx(15.0)

    def test_province_count_is_reported_per_year(self, shifted_istat_csv):
        raw = production.load_raw_istat(shifted_istat_csv)
        series = production.build_piedmont_series(raw)
        assert set(series["n_provinces"]) == {2}

    def test_years_are_sorted_ascending(self, shifted_istat_csv):
        raw = production.load_raw_istat(shifted_istat_csv)
        series = production.build_piedmont_series(raw)
        assert series["year"].is_monotonic_increasing

    def test_raises_when_no_piedmont_rows_match(self):
        """A silent empty frame here would produce an empty dashboard, so the
        pipeline is expected to fail loudly instead."""
        raw = pd.DataFrame({
            "region_code": ["ITF33"], "region_name": ["Napoli"], "crop": ["WINEES"],
            "year": [2020], "production": [1.0], "area_ha": [1.0], "yield_per_ha": [1.0],
        })
        with pytest.raises(ValueError, match="No Piedmont province rows"):
            production.build_piedmont_series(raw)


class TestBuildProvinceSeries:
    def test_nuts3_code_is_preserved_for_the_geojson_join(self, shifted_istat_csv):
        """The choropleth joins on ``NUTS_ID``, so the code column must survive."""
        raw = production.load_raw_istat(shifted_istat_csv)
        prov = production.build_province_series(raw)
        assert set(prov["region_code"]) == {"ITC16", "ITC17"}

    def test_yield_deviation_is_relative_to_each_province(self, shifted_istat_csv):
        """``yield_vs_mean_pct`` is a within-province deviation, so it must
        average to zero inside each province rather than across the region."""
        raw = production.load_raw_istat(shifted_istat_csv)
        prov = production.build_province_series(raw)

        per_province = prov.groupby("region_code")["yield_vs_mean_pct"].mean()
        for code, mean_dev in per_province.items():
            assert mean_dev == pytest.approx(0.0, abs=1e-9), code

    def test_every_configured_province_is_attempted(self):
        """Guard against the config list and the pipeline drifting apart."""
        assert len(config.PIEDMONT_PROVINCE_CODES) == 7
        assert all(code.startswith("ITC1") for code in config.PIEDMONT_PROVINCE_CODES)
        assert "ITC11" not in config.PIEDMONT_PROVINCE_CODES  # Torino absent from the extract
