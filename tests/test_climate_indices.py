"""Tests for the annual climate indices.

Two properties carry real risk here. The seasonal windows must be respected, so
a hot day in May cannot inflate the summer heatwave count; and the heatwave
threshold must be applied strictly, because a day sitting exactly on the
threshold is not a heatwave day under the stated definition.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from src import climate_indices


class TestHeatwaveDays:
    def test_counts_only_days_above_the_threshold(self, daily_builder):
        """July at 35 C is 31 heatwave days; nothing else qualifies."""
        tmax, precip = daily_builder(2020, {7: 35.0}, {})
        out = climate_indices.compute_indices(tmax, precip)
        assert out.loc[0, "summer_heatwave_days"] == 31

    def test_ignores_hot_days_outside_the_summer_window(self, daily_builder):
        """A hot May does not count: the index is defined over JJA only."""
        tmax, precip = daily_builder(2020, {5: 40.0}, {})
        out = climate_indices.compute_indices(tmax, precip)
        assert out.loc[0, "summer_heatwave_days"] == 0
        assert 5 not in config.SUMMER_MONTHS

    def test_threshold_is_strict(self, daily_builder):
        """A day exactly at HEAT_TMAX_THRESHOLD_C is not a heatwave day.

        This pins the boundary. Relaxing the comparison to >= would add days in
        most years and shift the quartile cut that defines a heat year, which
        propagates all the way to the headline figure.
        """
        at_threshold = config.HEAT_TMAX_THRESHOLD_C
        tmax, precip = daily_builder(2020, {7: at_threshold}, {})
        out = climate_indices.compute_indices(tmax, precip)
        assert out.loc[0, "summer_heatwave_days"] == 0

        tmax, precip = daily_builder(2020, {7: at_threshold + 0.1}, {})
        out = climate_indices.compute_indices(tmax, precip)
        assert out.loc[0, "summer_heatwave_days"] == 31

    def test_sums_across_all_three_summer_months(self, daily_builder):
        tmax, precip = daily_builder(2020, {6: 35.0, 7: 35.0, 8: 35.0}, {})
        out = climate_indices.compute_indices(tmax, precip)
        assert out.loc[0, "summer_heatwave_days"] == 30 + 31 + 31


class TestGrowingSeasonPrecipitation:
    def test_totals_only_the_growing_season(self, daily_builder):
        """10 mm a day through Apr-Sep, and 100 mm a day outside it.

        Only the growing-season days should be counted, so a wet winter cannot
        disguise a dry summer.
        """
        inside = {m: 10.0 for m in config.GROWING_SEASON_MONTHS}
        outside = {m: 100.0 for m in range(1, 13)
                   if m not in config.GROWING_SEASON_MONTHS}
        tmax, precip = daily_builder(2020, {}, {**inside, **outside})

        out = climate_indices.compute_indices(tmax, precip)
        days_in_season = sum(
            pd.Period(f"2020-{m:02d}").days_in_month
            for m in config.GROWING_SEASON_MONTHS)
        assert out.loc[0, "growing_precip_mm"] == pytest.approx(10.0 * days_in_season)

    def test_precipitation_is_summed_not_averaged(self, daily_builder):
        tmax, precip = daily_builder(2020, {}, {m: 2.0 for m in range(1, 13)})
        out = climate_indices.compute_indices(tmax, precip)
        assert out.loc[0, "growing_precip_mm"] > 100.0  # a mean would give 2.0


class TestMonthlyColumns:
    def test_one_column_per_growing_season_month(self, daily_builder):
        tmax, precip = daily_builder(2020, {}, {})
        out = climate_indices.compute_indices(tmax, precip)
        for m in config.GROWING_SEASON_MONTHS:
            assert f"tmax_m{m:02d}" in out.columns
            assert f"precip_m{m:02d}" in out.columns

    def test_monthly_tmax_is_a_mean_and_precip_a_total(self, daily_builder):
        tmax, precip = daily_builder(2020, {6: 30.0}, {6: 5.0})
        out = climate_indices.compute_indices(tmax, precip)
        assert out.loc[0, "tmax_m06"] == pytest.approx(30.0)
        assert out.loc[0, "precip_m06"] == pytest.approx(5.0 * 30)

    def test_missing_month_yields_nan_rather_than_zero(self):
        """A month with no observations must not read as a cold, dry month."""
        idx = pd.date_range("2020-06-01", "2020-06-30", freq="D")
        tmax = pd.Series(25.0, index=idx)
        precip = pd.Series(2.0, index=idx)
        out = climate_indices.compute_indices(tmax, precip)
        assert np.isnan(out.loc[0, "tmax_m07"])
        assert np.isnan(out.loc[0, "precip_m07"])


class TestMultipleYears:
    def test_one_row_per_year_sorted_ascending(self, daily_builder):
        frames = [daily_builder(y, {7: 33.0}, {}) for y in (2008, 2006, 2007)]
        tmax = pd.concat([f[0] for f in frames]).sort_index()
        precip = pd.concat([f[1] for f in frames]).sort_index()

        out = climate_indices.compute_indices(tmax, precip)
        assert out["year"].tolist() == [2006, 2007, 2008]

    def test_years_are_computed_independently(self, daily_builder):
        hot = daily_builder(2006, {7: 35.0}, {})
        mild = daily_builder(2007, {7: 20.0}, {})
        tmax = pd.concat([hot[0], mild[0]])
        precip = pd.concat([hot[1], mild[1]])

        out = climate_indices.compute_indices(tmax, precip).set_index("year")
        assert out.loc[2006, "summer_heatwave_days"] == 31
        assert out.loc[2007, "summer_heatwave_days"] == 0

    def test_index_is_source_agnostic(self, daily_builder):
        """``compute_indices`` is shared by the ERA5 and Open-Meteo paths, so it
        must depend only on the two daily series it is handed."""
        tmax, precip = daily_builder(2020, {7: 35.0}, {})
        first = climate_indices.compute_indices(tmax, precip)
        second = climate_indices.compute_indices(tmax.copy(), precip.copy())
        pd.testing.assert_frame_equal(first, second)
