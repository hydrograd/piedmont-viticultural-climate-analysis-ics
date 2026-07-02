"""Central configuration for the Piedmont viticultural climate analysis.

All file paths, the study region, and the analysis thresholds are defined here so
the pipeline is reproducible and can be retargeted to another region or window by
editing this file alone.
"""
from pathlib import Path

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
for _p in (DATA_PROCESSED, OUTPUTS):
    _p.mkdir(parents=True, exist_ok=True)

# Raw inputs
ISTAT_CSV = DATA_RAW / "filtered_processed_istat_GRAPES.csv"

# Processed outputs
PRODUCTION_CSV = DATA_PROCESSED / "piedmont_production.csv"
PRODUCTION_BY_PROVINCE_CSV = DATA_PROCESSED / "piedmont_production_by_province.csv"
CLIMATE_CSV = DATA_PROCESSED / "piedmont_climate_indices.csv"
COMPOUND_CSV = DATA_PROCESSED / "piedmont_compound_analysis.csv"

# Province polygons used by the dashboard choropleth
PIEDMONT_GEOJSON = ROOT / "data" / "geo" / "piedmont_nuts3.geojson"

# --- Study region ----------------------------------------------------------
REGION_NAME = "Piedmont"

# NUTS-3 province codes that make up Piedmont in the ISTAT extract. Torino
# (ITC11) is not present in the supplied data, so the region total is the sum of
# these seven provinces.
PIEDMONT_PROVINCE_CODES = [
    "ITC12",  # Vercelli
    "ITC13",  # Biella
    "ITC14",  # Verbano-Cusio-Ossola
    "ITC15",  # Novara
    "ITC16",  # Cuneo (major wine province)
    "ITC17",  # Asti (major wine province)
    "ITC18",  # Alessandria
]

# Bounding box for the CDS/ERA5 area-subset download: [North, West, South, East].
PIEDMONT_BBOX = [46.5, 6.6, 44.0, 9.3]

# Sampling points for the Open-Meteo ingest (name, lat, lon). These sit in the
# main wine districts (the grape-growing hills and valleys). Province centroids
# were avoided because several fall in the Alps and badly misrepresent the
# climate the vines actually experience.
WINE_DISTRICTS = [
    ("Langhe (Alba)", 44.70, 8.04),              # Barolo / Barbaresco, Cuneo
    ("Roero", 44.80, 7.95),                      # Cuneo, north of Alba
    ("Monferrato (Asti)", 44.90, 8.21),          # Asti
    ("Acqui / Monferrato", 44.68, 8.47),         # Asti / Alessandria border
    ("Gavi / Tortonese", 44.76, 8.80),           # Alessandria
    ("Alto Piemonte (Gattinara)", 45.62, 8.36),  # Vercelli / Novara hills
]

# --- Climate index definitions --------------------------------------------
# A heatwave day is a summer day with regional-mean daily-max temperature above
# this threshold (Celsius).
HEAT_TMAX_THRESHOLD_C = 32.0
SUMMER_MONTHS = [6, 7, 8]                     # JJA, the heat-stress window
GROWING_SEASON_MONTHS = [4, 5, 6, 7, 8, 9]    # Apr to Sep, the drought-relevant window

# A compound event is treated as an extreme, so a "heat year" or "drought year"
# is one in the top / bottom this-fraction of years. 0.25 = quartile (severe);
# 0.33 = tercile (looser). This is the largest single lever on the headline
# result; see ANALYSIS.md for the sensitivity (dose-response).
COMPOUND_SEVERITY_PCTL = 0.25

# Climate window. Defaults to the production overlap (2006-2023). The climate
# sources reach back to 1940, so extending CLIMATE_START_YEAR gives a longer
# record (e.g. for anomaly baselines or a long-term stress trend); the ingest
# code simply covers more years.
CLIMATE_START_YEAR = 2006
CLIMATE_END_YEAR = 2023

# Years used in the joined analysis (production and climate overlap).
ANALYSIS_START_YEAR = 2006
ANALYSIS_END_YEAR = 2023
