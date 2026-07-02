"""Generator for the project's Jupyter notebooks.

Run once (``python build_notebooks.py``) to (re)create the numbered notebooks in
notebooks/. Generating them from a single script keeps them consistent; the
analysis logic lives in src/ and is imported, so the notebooks stay thin.
"""
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
from pathlib import Path

NB_DIR = Path(__file__).resolve().parent / "notebooks"
NB_DIR.mkdir(exist_ok=True)

# Reused at the top of every notebook: locate the project root (the folder with
# config.py) and make it importable, so notebooks run from notebooks/ directly.
BOOTSTRAP = '''# Locate the project root and make src/ + config importable.
import os, sys
d = os.getcwd()
while not os.path.exists(os.path.join(d, "config.py")) and os.path.dirname(d) != d:
    d = os.path.dirname(d)
os.chdir(d)
if d not in sys.path:
    sys.path.insert(0, d)
print("Project root:", d)'''


def md(text):
    return new_markdown_cell(text)


def code(text):
    return new_code_cell(text)


def write(nb, name):
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nbf.write(nb, str(NB_DIR / name))
    print("wrote", name)


# ===========================================================================
# 01 - Production and EDA
# ===========================================================================
nb = new_notebook(cells=[
    md("""# 01 - Grape production: load, clean, explore

Turns the raw ISTAT extract into a clean annual production series for Piedmont
(regional total and per-province) and explores it. No external data or API key is
needed for this notebook."""),
    code("# Install dependencies once (uncomment to run):\n# !pip install -q -r requirements.txt"),
    code(BOOTSTRAP),
    code("import pandas as pd\nimport matplotlib.pyplot as plt\nimport config\nfrom src import production\npd.set_option('display.width', 120)"),
    md("""## 1. The source file has a mislabelled header

In the raw CSV the column headings are shifted one place: the column labelled
`Year` holds the crop name, and `Crop` holds the year. `production.load_raw_istat`
corrects this, but it is worth seeing first-hand."""),
    code("raw_uncorrected = pd.read_csv(config.ISTAT_CSV)\nprint('Columns as labelled:', list(raw_uncorrected.columns))\nraw_uncorrected.head(3)"),
    code("# Row 0, field by field: 'Year' holds 'WINEES' (crop) and 'Crop' holds 2006 (year).\nraw_uncorrected.iloc[0]"),
    md("""## 2. Load with corrected columns"""),
    code("df = production.load_raw_istat()\nprint('Corrected columns:', list(df.columns))\ndf.head(3)"),
    md("""## 3. Build the Piedmont series

Piedmont is the sum of 7 NUTS-3 provinces (Torino is absent from the extract).
Production and area are summed; yield is recomputed from the regional totals."""),
    code("piedmont = production.build_piedmont_series(df)\npiedmont"),
    code("# Persist for later notebooks.\npiedmont.to_csv(config.PRODUCTION_CSV, index=False)\nprint('saved ->', config.PRODUCTION_CSV)"),
    md("## 4. Exploratory data analysis"),
    code("""fig, ax = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
ax[0].plot(piedmont.year, piedmont.production/1e6, marker='o', color='#6a1b9a'); ax[0].set_ylabel('Production\\n(million q)')
ax[1].plot(piedmont.year, piedmont.yield_per_ha, marker='s', color='#2e7d32'); ax[1].set_ylabel('Yield (q/ha)')
ax[2].plot(piedmont.year, piedmont.area_ha, marker='^', color='#c62828'); ax[2].set_ylabel('Area (ha)'); ax[2].set_xlabel('Year')
for a in ax: a.grid(alpha=.3)
ax[0].set_title('Piedmont wine grapes, 2006 to 2023')
plt.tight_layout(); plt.show()"""),
    md("""Two points shape the rest of the analysis:

- Vineyard area declines (about 50k to 38k ha), a structural trend unrelated to
  weather. The climate analysis therefore works with yield per hectare, and
  detrends it, to isolate the weather signal.
- 2017 is the weakest year in the record, a known heat, drought and frost vintage
  in Italy, so a climate signal is plausibly present."""),
    code("""print('Yield summary (q/ha):'); print(piedmont.yield_per_ha.describe().round(1))
print('\\nLowest-yield years:'); print(piedmont.nsmallest(3, 'yield_per_ha')[['year','yield_per_ha','production']].to_string(index=False))"""),
    md("""Output: `data/processed/piedmont_production.csv` and
`..._by_province.csv`. Next, `02_climate_data.ipynb` builds the climate indices."""),
])
write(nb, "01_production_and_eda.ipynb")


# ===========================================================================
# 02 - Climate data
# ===========================================================================
nb = new_notebook(cells=[
    md("""# 02 - Climate data: fetch ERA5 and build indices

Fetches daily temperature and precipitation for the Piedmont wine districts
(2006 to 2023) and reduces each year to a set of climate indicators.

Source: the Open-Meteo historical API, whose archive is ERA5, delivered over a
fast HTTP API with no key and no request queue. The Copernicus CDS path
(`src/climate_ingest.py`) is kept as an official-source option but is slower."""),
    code(BOOTSTRAP),
    code("import os, glob, pandas as pd, matplotlib.pyplot as plt\nimport config\nfrom src import climate_ingest_openmeteo as om, climate_indices"),
    md("""## 1. Sampling points

We sample the wine districts (the hills and valleys where grapes grow) rather than
province centroids, several of which fall in the Alps and would bias the regional
climate cold. The points are defined in `config.WINE_DISTRICTS`."""),
    code("pd.DataFrame(config.WINE_DISTRICTS, columns=['district','lat','lon'])"),
    md("""## 2. Fetch and build indices

`om.main()` fetches daily max-temperature (pure ERA5 model) and precipitation for
each district, averages them into a regional series, computes the indices, and
writes `piedmont_climate_indices.csv`. Each district is cached under
`data/raw/openmeteo/`, so re-runs are fast and resilient to rate limits.

To use the CDS/ERA5 path instead: `from src import climate_ingest;
climate_ingest.main()` followed by `climate_indices.main()`."""),
    code("climate = om.main()"),
    code("# Cached per-district raw files (for reproducibility):\nsorted(os.path.basename(p) for p in glob.glob(str(config.DATA_RAW/'openmeteo'/'*.csv')))"),
    md("## 3. The yearly climate indices"),
    code("climate[['year','summer_heatwave_days','summer_mean_tmax_c','growing_precip_mm']]"),
    md("## 4. Climate EDA"),
    code("""fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
ax[0].bar(climate.year, climate.summer_heatwave_days, color='#ef6c00'); ax[0].set_ylabel('Heatwave days\\n(JJA, Tmax>%g C)' % config.HEAT_TMAX_THRESHOLD_C)
ax[1].bar(climate.year, climate.growing_precip_mm, color='#1565c0'); ax[1].set_ylabel('Apr-Sep rain (mm)'); ax[1].set_xlabel('Year')
for a in ax: a.grid(alpha=.3, axis='y')
ax[0].set_title('Piedmont climate stress indicators')
plt.tight_layout(); plt.show()"""),
    md("""Output: `data/processed/piedmont_climate_indices.csv`. Next,
`03_compound_analysis.ipynb` joins this to production."""),
])
write(nb, "02_climate_data.ipynb")


# ===========================================================================
# 03 - Compound analysis
# ===========================================================================
nb = new_notebook(cells=[
    md("""# 03 - Compound events and the production-risk comparison

Classifies each year (normal / heat_only / drought_only / concurrent / sequential)
and compares yield in compound years against normal years.

Requires `piedmont_production.csv` (nb 01) and `piedmont_climate_indices.csv`
(nb 02)."""),
    code(BOOTSTRAP),
    code("import numpy as np, pandas as pd, matplotlib.pyplot as plt\nimport config\nfrom src import compound"),
    md("""## 1. How a year is classified

A compound event is treated as an extreme, so severity uses the top/bottom
`config.COMPOUND_SEVERITY_PCTL` fraction of years (default 0.25, i.e. quartile):

- Heat year: summer heatwave-days in the hottest quartile.
- Drought year: growing-season rainfall in the driest quartile.
- Concurrent: a single month that is both hot and dry.
- Sequential: heat and drought in different months, not overlapping.
- Normal: neither, used as the comparison group.

`COMPOUND_SEVERITY_PCTL` is the largest lever on the result. Section 4 shows the
sensitivity (the dose-response); see ANALYSIS.md for the full discussion."""),
    code("merged = compound.build()\nmerged.to_csv(config.COMPOUND_CSV, index=False)\nmerged[['year','yield_per_ha','yield_anom_pct','summer_heatwave_days','growing_precip_mm','category']]"),
    md("## 2. The headline comparison"),
    code("""h = compound.headline(merged)
print('Compound-event years (%d): %s' % (h['n_compound'], h['compound_years']))
print('Normal years: %d' % h['n_normal'])
if h['pct_difference'] == h['pct_difference']:
    d = 'lower' if h['pct_difference'] < 0 else 'higher'
    print('\\nIn compound-event years, Piedmont yield was %.1f%% %s than in normal years' % (abs(h['pct_difference']), d))
    print('(%.1f vs %.1f quintals/ha).' % (h['mean_yield_compound'], h['mean_yield_normal']))
else:
    print('Not enough compound or normal years; widen the record or revisit thresholds.')"""),
    md("## 3. Sensitivity: the dose-response"),
    code("""rows = []
for pctl, label in [(1/3, 'tercile (loose)'), (0.25, 'quartile'), (0.20, 'top/bottom 20%')]:
    prev = config.COMPOUND_SEVERITY_PCTL
    config.COMPOUND_SEVERITY_PCTL = pctl
    m = compound.build(); hh = compound.headline(m)
    config.COMPOUND_SEVERITY_PCTL = prev
    rows.append({'definition': label, 'compound_years': hh['compound_years'], 'pct_diff': round(hh['pct_difference'], 1)})
pd.DataFrame(rows)"""),
    md("## 4. Yield timeline with compound years marked"),
    code("""colors = {'normal':'#9e9e9e','heat_only':'#ef6c00','drought_only':'#fbc02d','concurrent':'#c62828','sequential':'#6a1b9a'}
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(merged.year, merged.yield_per_ha, color='#455a64', zorder=1)
for cat, c in colors.items():
    sub = merged[merged.category == cat]
    ax.scatter(sub.year, sub.yield_per_ha, s=120, color=c, label=cat, zorder=2, edgecolor='white')
ax.set_xlabel('Year'); ax.set_ylabel('Yield (q/ha)'); ax.legend(title='Year type', ncol=2)
ax.set_title('Piedmont grape yield, with compound-event years marked'); ax.grid(alpha=.3)
plt.tight_layout(); plt.show()"""),
    md("""Output: `data/processed/piedmont_compound_analysis.csv`. Next,
`04_dashboard.ipynb` presents this interactively."""),
])
write(nb, "03_compound_analysis.ipynb")


# ===========================================================================
# 04 - Dashboard
# ===========================================================================
nb = new_notebook(cells=[
    md("""# 04 - Launch the interactive dashboard

The dashboard is a map-led Streamlit app: an animated province choropleth, the
compound-event comparison, a yield timeline, and a per-year event ribbon. Its code
is in `app.py` and its theme in `.streamlit/config.toml`.

Streamlit runs as its own web server, so it cannot execute inside a notebook cell.
This notebook launches `app.py` in the background and prints a local URL."""),
    code(BOOTSTRAP),
    md("## 1. Inspect the app source (optional)"),
    code("print(open('app.py').read()[:1200])"),
    md("## 2. Launch (runs in the background and prints a URL)"),
    code('''import subprocess, time, sys, urllib.request
PORT = 8501
proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py",
                         "--server.headless=true", f"--server.port={PORT}"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
url = f"http://localhost:{PORT}"
for _ in range(30):
    time.sleep(1)
    try:
        if urllib.request.urlopen(url + "/_stcore/health", timeout=2).status == 200:
            break
    except Exception:
        pass
print("Dashboard running at:", url)'''),
    md("## 3. Stop the server when finished"),
    code('proc.terminate()\nprint("stopped")'),
])
write(nb, "04_dashboard.ipynb")

print("\nAll notebooks generated in", NB_DIR)
