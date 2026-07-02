# Raw data inputs

This folder holds raw inputs, which are **not committed** to the repository (see
`.gitignore`). Place the source files here locally before running the pipeline.

## Required input

`filtered_processed_istat_GRAPES.csv`

ISTAT wine-grape production statistics by NUTS-3 province, 2006 to 2023. This is
the ICS-supplied ISTAT extract. It contains one row per province and year, with
production, harvested area, and yield.

Note: the header row in this file is shifted one column to the left of the values
it labels (for example, the column labelled `Observation` actually holds
production, and `Amount` holds area). `src/production.py` documents and corrects
this mapping on load, so use the file as delivered without editing the header.

## Generated files (also not committed)

The climate ingest scripts write here and can be regenerated at any time:

- `openmeteo/` : cached Open-Meteo API responses (default climate path)
- `era5/`      : NetCDF downloads from the Copernicus CDS (optional path)

## Reproducing without the raw ISTAT file

The processed outputs in `data/processed/` are committed, so the climate,
compound-analysis, and dashboard stages run without the raw ISTAT file. Only
notebook 01 (and `python -m src.production`) needs the raw input to rebuild the
production series from scratch.
