# Piedmont Viticultural Climate Analysis

How do heatwaves and rainfall deficits, alone and as **compound events**
(concurrent or sequential), affect wine-grape production in **Piedmont, Italy**?

This project pairs ISTAT grape-production statistics with ERA5 reanalysis climate
data, classifies each year by its climate stress, and quantifies the effect on
yield. The result is presented in an interactive Streamlit dashboard (an animated
province choropleth with a year slider, the compound-event comparison, a yield
timeline, and a per-year event ribbon).

**Key finding:** in severe compound heat-and-drought years (2017 and 2022),
Piedmont grape yield was about 5% lower than in normal years, and the penalty
deepens as the events become more severe. The signal is driven by extreme heat;
drought alone shows little effect. See [ANALYSIS.md](ANALYSIS.md) for the full
method, results, and caveats.

---

## Repository layout

```
config.py                 all paths, region, and analysis thresholds
src/
  production.py           load and clean ISTAT, build production series
  climate_ingest_openmeteo.py   climate ingest via Open-Meteo (default)
  climate_ingest.py       climate ingest via Copernicus CDS (optional)
  climate_indices.py      daily series -> annual climate indices
  compound.py             compound-event classification and comparison
  plots.py                static inspection plots
app.py                    Streamlit dashboard
build_notebooks.py        regenerates the notebooks below
notebooks/                01 production, 02 climate, 03 compound, 04 dashboard
data/                     raw inputs (git-ignored) and processed CSVs
ANALYSIS.md               the science: data, method, results, limitations
WALKTHROUGH.md            developer walkthrough of the repo
```

The notebooks are the recommended entry point; they import the tested modules in
`src/`. Everything configurable lives in `config.py`.

## Quick start

```bash
pip install -r requirements.txt
jupyter notebook          # open notebooks/ and run 01 to 04 in order
```

No API key is required: the climate data comes from the free Open-Meteo historical
API, which serves ERA5. The modules can also be run directly:

```bash
python -m src.production
python -m src.climate_ingest_openmeteo
python -m src.compound
streamlit run app.py
```

## Climate data source

**Default: Open-Meteo** (`src/climate_ingest_openmeteo.py`). Free, no key, no
queue; its historical archive is ERA5. Sampling uses the Piedmont wine districts
(`config.WINE_DISTRICTS`) rather than province centroids, several of which fall in
the Alps and would bias the regional climate.

**Optional: Copernicus CDS / ERA5** (`src/climate_ingest.py`). The official-source
path, kept for cross-checking. It needs a free CDS account and can be slow (the
request queue often takes minutes to tens of minutes). To use it:

1. Register at https://cds.climate.copernicus.eu and accept the licence on the
   *ERA5 daily statistics* dataset (`derived-era5-single-levels-daily-statistics`).
2. Create `~/.cdsapirc`:
   ```
   url: https://cds.climate.copernicus.eu/api
   key: <your-key>
   ```
3. `pip install cdsapi` (already in `requirements.txt`), then
   `python -m src.climate_ingest` followed by `python -m src.climate_indices`.

## Data notes and decisions

- **Mislabelled ISTAT header.** The source CSV's column headings are shifted one
  place; `src/production.py` documents and corrects the true mapping.
- **Piedmont = 7 NUTS-3 provinces** (Torino is absent from the extract), summed to
  a regional total. A per-province breakdown feeds the dashboard map.
- **ERA5 rather than CERRA.** CERRA is higher resolution (5.5 km) but its
  precipitation is a separate dataset and downloads are large. Because the analysis
  averages over the region, ERA5 gives the same signal far more cheaply. See
  ANALYSIS.md, section 3.
- **Yield is detrended** before the comparison, to separate climate sensitivity
  from the long-run decline in vineyard area.

The raw ISTAT production file, the climate downloads, and the API cache are all
git-ignored; see `data/raw/README.md` for what to place there. The processed CSVs
under `data/processed/` are committed, so the climate, compound, and dashboard
stages run from a clean checkout without the raw ISTAT input.

## Author

Shrey Shukla ([LinkedIn](https://www.linkedin.com/in/shreysshukla))

## License

Released under the MIT License; see [LICENSE](LICENSE).
