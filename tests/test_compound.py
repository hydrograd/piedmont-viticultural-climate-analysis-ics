"""Tests for compound-event classification and the headline comparison.

The detrending is the step the headline result rests on. Harvested area falls
roughly a quarter across the record for reasons that are structural rather than
meteorological, so a comparison of raw yields would attribute part of that
decline to the weather. The tests below pin the property that matters: a series
containing only a trend must produce no anomaly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from src import compound


class TestExtremeFlags:
    def test_warm_side_flags_the_top_fraction(self):
        values = pd.Series([1, 2, 3, 4, 5, 6, 7, 8], dtype=float)
        flags = compound._extreme_flags(values, warm_side=True, pctl=0.25)
        assert flags.tolist() == [False] * 6 + [True, True]

    def test_cold_side_flags_the_bottom_fraction(self):
        values = pd.Series([1, 2, 3, 4, 5, 6, 7, 8], dtype=float)
        flags = compound._extreme_flags(values, warm_side=False, pctl=0.25)
        assert flags.tolist() == [True, True] + [False] * 6

    def test_a_looser_percentile_flags_more_years(self):
        """The severity percentile is the largest single lever on the result, so
        its direction of effect is worth pinning."""
        values = pd.Series(range(12), dtype=float)
        quartile = compound._extreme_flags(values, True, 0.25).sum()
        tercile = compound._extreme_flags(values, True, 1 / 3).sum()
        assert tercile > quartile


class TestClassifyYears:
    def test_every_year_gets_exactly_one_known_category(self, climate_frame_builder):
        climate = climate_frame_builder(
            heatwave_days=[0, 2, 4, 6, 8, 10, 25, 30],
            growing_precip=[500, 450, 400, 350, 300, 250, 120, 100])
        out = compound.classify_years(climate)

        allowed = {"normal", "heat_only", "drought_only", "concurrent", "sequential"}
        assert set(out["category"]) <= allowed
        assert out["category"].notna().all()
        assert len(out) == len(climate)

    def test_is_compound_agrees_with_the_category(self, climate_frame_builder):
        climate = climate_frame_builder(
            heatwave_days=[0, 2, 4, 6, 8, 10, 25, 30],
            growing_precip=[500, 450, 400, 350, 300, 250, 120, 100])
        out = compound.classify_years(climate)

        expected = out["category"].isin(["concurrent", "sequential"])
        assert out["is_compound"].tolist() == expected.tolist()

    def test_hot_and_dry_year_is_compound(self, climate_frame_builder):
        """The last year is both the hottest and the driest, so it must be
        classified as one of the two compound categories."""
        climate = climate_frame_builder(
            heatwave_days=[0, 1, 2, 3, 4, 5, 6, 40],
            growing_precip=[500, 490, 480, 470, 460, 450, 440, 50])
        out = compound.classify_years(climate).set_index("year")
        last = out.index.max()
        assert out.loc[last, "is_compound"]

    def test_hot_but_wet_year_is_heat_only(self, climate_frame_builder):
        climate = climate_frame_builder(
            heatwave_days=[0, 1, 2, 3, 4, 5, 6, 40],
            growing_precip=[100, 200, 300, 350, 400, 450, 480, 900])
        out = compound.classify_years(climate).set_index("year")
        last = out.index.max()
        assert out.loc[last, "category"] == "heat_only"
        assert not out.loc[last, "is_compound"]

    def test_dry_but_cool_year_is_drought_only(self, climate_frame_builder):
        climate = climate_frame_builder(
            heatwave_days=[40, 30, 20, 10, 8, 6, 4, 0],
            growing_precip=[900, 800, 700, 600, 500, 400, 300, 50])
        out = compound.classify_years(climate).set_index("year")
        last = out.index.max()
        assert out.loc[last, "category"] == "drought_only"

    def test_mild_year_is_normal(self, climate_frame_builder):
        climate = climate_frame_builder(
            heatwave_days=[0, 1, 2, 3, 4, 5, 6, 40],
            growing_precip=[100, 200, 300, 400, 410, 420, 430, 440])
        out = compound.classify_years(climate)
        assert "normal" in set(out["category"])

    def test_overlapping_hot_dry_month_reads_as_concurrent(self, climate_frame_builder):
        """A single month that is both in the hottest and the driest tercile is
        what separates concurrent stress from stress arriving in sequence."""
        n = 8
        monthly_tmax = {m: [20.0] * n for m in config.GROWING_SEASON_MONTHS}
        monthly_precip = {m: [50.0] * n for m in config.GROWING_SEASON_MONTHS}
        # Make July of the final year both the hottest and the driest July.
        monthly_tmax[7] = [20.0] * (n - 1) + [40.0]
        monthly_precip[7] = [50.0] * (n - 1) + [1.0]

        climate = climate_frame_builder(
            heatwave_days=[0, 1, 2, 3, 4, 5, 6, 40],
            growing_precip=[500, 490, 480, 470, 460, 450, 440, 50],
            monthly_tmax=monthly_tmax, monthly_precip=monthly_precip)
        out = compound.classify_years(climate).set_index("year")
        assert out.loc[out.index.max(), "category"] == "concurrent"


class TestDetrendYield:
    def test_a_pure_linear_series_has_no_anomaly(self, production_frame_builder):
        """The core property. If yield follows the trend exactly, the detrended
        anomaly is zero everywhere and no year looks like a climate signal."""
        years = range(2006, 2024)
        yields = [100.0 - 1.5 * (y - 2006) for y in years]
        out = compound.detrend_yield(production_frame_builder(years, yields))
        assert out["yield_anom_pct"].abs().max() == pytest.approx(0.0, abs=1e-8)

    def test_structural_decline_does_not_become_an_anomaly(self, production_frame_builder):
        """A 24% fall spread evenly across the record is trend, not signal."""
        years = list(range(2006, 2024))
        start, end = 100.0, 76.0
        step = (end - start) / (len(years) - 1)
        yields = [start + step * i for i in range(len(years))]

        out = compound.detrend_yield(production_frame_builder(years, yields))
        assert out["yield_per_ha"].iloc[-1] / out["yield_per_ha"].iloc[0] == pytest.approx(0.76)
        assert out["yield_anom_pct"].abs().max() < 1e-6

    def test_a_single_bad_year_shows_as_a_negative_anomaly(self, production_frame_builder):
        years = list(range(2006, 2024))
        yields = [100.0] * len(years)
        yields[10] = 80.0  # one poor harvest against a flat trend

        out = compound.detrend_yield(production_frame_builder(years, yields))
        assert out["yield_anom_pct"].iloc[10] < -10.0
        assert out["yield_anom_pct"].drop(index=10).max() > 0

    def test_trend_column_is_added_without_dropping_inputs(self, production_frame_builder):
        years = range(2006, 2016)
        out = compound.detrend_yield(
            production_frame_builder(years, [100.0] * 10))
        assert {"yield_trend", "yield_anom_pct"} <= set(out.columns)
        assert "yield_per_ha" in out.columns


class TestHeadline:
    def _merged(self, categories, anomalies, yields):
        return pd.DataFrame({
            "year": range(2006, 2006 + len(categories)),
            "category": categories,
            "is_compound": [c in ("concurrent", "sequential") for c in categories],
            "yield_per_ha": yields,
            "yield_anom_pct": anomalies,
        })

    def test_reports_the_gap_between_compound_and_normal_years(self):
        merged = self._merged(
            categories=["normal", "normal", "concurrent", "sequential"],
            anomalies=[2.0, 2.0, -5.0, -5.0],
            yields=[100.0, 100.0, 90.0, 90.0])
        out = compound.headline(merged)

        assert out["n_compound"] == 2
        assert out["n_normal"] == 2
        assert out["pct_difference"] == pytest.approx(-10.0)
        assert out["anom_gap_pts"] == pytest.approx(-7.0)

    def test_compound_years_are_listed_for_the_dashboard(self):
        merged = self._merged(
            categories=["normal", "concurrent", "normal", "sequential"],
            anomalies=[0.0, -5.0, 0.0, -5.0],
            yields=[100.0, 90.0, 100.0, 90.0])
        out = compound.headline(merged)
        assert out["compound_years"] == [2007, 2009]

    def test_returns_nan_rather_than_dividing_by_an_empty_group(self):
        """With no compound years the comparison is undefined. It must come back
        as NaN so the dashboard can say so, rather than raising or reporting a
        figure built on nothing."""
        merged = self._merged(
            categories=["normal", "normal", "heat_only"],
            anomalies=[0.0, 1.0, -2.0],
            yields=[100.0, 101.0, 98.0])
        out = compound.headline(merged)

        assert out["n_compound"] == 0
        assert np.isnan(out["pct_difference"])
        assert np.isnan(out["anom_gap_pts"])

    def test_counts_sum_to_the_record_length(self):
        merged = self._merged(
            categories=["normal", "concurrent", "heat_only", "drought_only"],
            anomalies=[0.0, -5.0, -1.0, -2.0],
            yields=[100.0, 90.0, 99.0, 98.0])
        out = compound.headline(merged)
        assert out["n_total"] == 4
        assert out["n_compound"] + out["n_normal"] <= out["n_total"]


class TestAnalysisWindow:
    def test_window_bounds_are_consistent(self):
        assert config.ANALYSIS_START_YEAR == 2006
        assert config.ANALYSIS_END_YEAR == 2023
        assert config.ANALYSIS_START_YEAR < config.ANALYSIS_END_YEAR
        span = config.ANALYSIS_END_YEAR - config.ANALYSIS_START_YEAR + 1
        assert span == 18  # the record the headline is reported over

    def test_severity_percentile_is_a_fraction(self):
        assert 0.0 < config.COMPOUND_SEVERITY_PCTL < 0.5
