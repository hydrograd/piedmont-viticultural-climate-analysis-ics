# The science behind the Piedmont grape climate-risk analysis

This document explains the **analysis itself**, the data, the choices, the
methods, and the concepts, rather than how the code is organised (for that, see
`WALKTHROUGH.md`). It sets out where the signal is real, where it is fragile, and
what would come next.

---

## 1. The question

> How do **heatwaves** and **rainfall deficits**, individually, and as **compound
> events** (heat and drought together), affect wine-grape production in Piedmont?

"Compound" is the operative word. Climate impacts are often **non-linear**: a hot
summer is survivable, a dry summer is survivable, but the two *together* can push
a system past a threshold it would tolerate separately. The analysis is built to
test whether that interaction is visible in Piedmont's grape record.

---

## 2. The data

### 2.1 Grape production, ISTAT
- **Source:** ISTAT (Italian national statistics), wine-grape production by NUTS-3
  province, **2006–2023**.
- **What we use:** production (quintals; 1 q = 100 kg), harvested area (hectares),
  and **yield = production ÷ area** (q/ha).
- **Piedmont = 7 provinces** (Cuneo, Asti, Alessandria, Novara, Vercelli, Biella,
  Verbano) summed to a regional series. Turin is absent from the extract.
- **Data-quality note:** the source CSV had a **one-column-shifted header**, the
  column labelled `Observation` actually held production, `Amount` held area, and
  so on. Every downstream number would have been wrong if taken at face value;
  the loader corrects the mapping explicitly.
- **Why yield, and why detrended:** harvested **area fell ~24%** over the period
  (≈50,000 → 38,000 ha) for economic/structural reasons unrelated to weather. Raw
  *production* therefore carries a strong non-climate downward trend. **Yield per
  hectare** removes the area effect; we then **linearly detrend** yield so the
  residual reflects year-to-year climate sensitivity rather than any slow trend.

### 2.2 Climate, reanalysis
We need, for every year, **daily maximum temperature** and **daily precipitation**
over the Piedmont wine region. We use **ERA5** reanalysis (0.25°, hourly,
1940–present, global), delivered via **Open-Meteo's historical API**.

---

## 3. Why not CERRA or ERA5-via-Copernicus directly?

Reanalysis "products" reconstruct past weather by blending a physical model with
historical observations onto a regular grid. Three were on the table:

| Product | Resolution | Coverage | Verdict |
|---------|-----------|----------|----------------------|
| **CERRA** | 5.5 km | Europe, 1984– | Highest resolution, but **precipitation lives in a separate dataset** (CERRA-Land), the grid is Lambert-conformal (awkward to subset), and downloads come in **multi-GB whole-domain chunks** (one year of one variable ≈ 4.7 GB). |
| **ERA5 via Copernicus CDS** | 0.25° (~31 km) | Global, 1940– | The "official" route, and area-subsettable, but the CDS **request queue took 25–40 minutes per request** when busy, and large multi-year requests were rejected on **cost limits**. Real but slow. |
| **ERA5 via Open-Meteo** | 0.25° | Global, 1940– | **Same ERA5 data**, delivered through a free, no-key, no-queue HTTP API. Seconds, not hours. |

**Decision:** ERA5, because the analysis **spatially averages over Piedmont**
anyway, so CERRA's 5.5 km resolution advantage largely washes out, and its
download cost is not justified here. Open-Meteo was chosen over the CDS API purely
for **delivery speed**; the underlying reanalysis is identical. The CDS path is
kept in the repo (`src/climate_ingest.py`) as an official-source cross-check.

**Two Open-Meteo data-quality issues, handled in the ingest:**
1. **Model choice matters.** The default (`best_match`) and ERA5-Land models have
   whole-year gaps over Piedmont (2006/2008/2011). The ingest requests the pure
   **ERA5** model, which is complete; the one variable/year it lacks (2017
   precipitation) is back-filled from `best_match`.
2. **Sampling location matters more.** **Province centroids** put points in the
   **Alps** (Verbano's centroid gives a 13 °C July max, a glacier, not a vineyard).
   The ingest instead samples **six wine districts** (Langhe, Roero, Monferrato,
   Acqui, Gavi, Alto Piemonte), the hills and valleys where grapes actually grow,
   and averages them (`config.WINE_DISTRICTS`). This is the difference between a
   physically meaningful climate series and a misleading one.

---

## 4. Features / metrics, and why each

| Feature | Definition | Rationale |
|---------|-----------|-----------|
| **Heatwave days** | Count of **JJA** days with wine-region-mean Tmax **> 32 °C** | Heat *stress* is driven by extreme days, not average warmth. (Note: ERA5 grid-cell daily max is an areal average, so it under-counts point-station extremes, fine for *relative* year-to-year ranking.) |
| **Summer mean Tmax** | Mean JJA daily-max temperature | A smoother "how warm overall" measure, for contrast. |
| **Growing-season precipitation** | **Apr–Sep** total rainfall (mm) | Water availability across the vine's active season; low values proxy drought. |
| **Yield anomaly** | Detrended yield, % from the linear trend | The **response** variable, climate sensitivity with the structural trend removed. |
| **Heat / drought severity flags** | Top / bottom **quartile** of years | An *event* implies an **extreme**, so quartile (not tercile) marks a "heat year" / "drought year". |
| **Compound type** | concurrent vs sequential (see §5) | The core scientific object. |

---

## 5. The analysis concepts

### 5.1 Defining a compound event
A year is classified in two stages:
1. **Year-level severity**, is it a *heat year* (heatwave days in the top
   quartile) and/or a *drought year* (growing-season rain in the bottom quartile)?
2. **Within-season timing**, for years flagged as *both*, is the stress
   **concurrent** (a single month that is both hot and dry) or **sequential** (a
   hot month directly followed by a dry one)?

Years then fall into: `normal`, `heat_only`, `drought_only`, `concurrent`,
`sequential`. `normal` is the comparison group.

Using **year-level** severity is deliberate: over an 18-year record almost every
year has *some* hot month and *some* dry month, so a purely monthly rule labels
nearly everything "compound" and leaves no baseline. (We saw exactly this, a
loose rule flagged 14 of 18 years and produced a meaningless comparison.)

### 5.2 The headline
> **In severe compound years (2017 and 2022), Piedmont grape yield was ~5.4%
> lower than in normal years** (74 vs 79 q/ha; ≈ −8 points on detrended anomaly).

### 5.3 Why it's credible, the dose-response
The finding is not a single lucky threshold. As the definition of "severe" is
tightened, the penalty **deepens monotonically**:

| Compound threshold | Compound years | Yield gap vs normal |
|--------------------|----------------|---------------------|
| Tercile (loose) | 2007, 2016, 2017, 2021, 2022 | −1.8 pts (≈ null) |
| **Quartile (severe)** | **2017, 2022** | **−8.3 pts** |
| Top/bottom 20% | 2017 | −12.3 pts |

Mild compound years are buffered (vines are resilient); **genuinely severe**
compound events cause real losses. A monotonic dose-response is much stronger
evidence than one hand-picked cut-off.

### 5.4 What's actually driving it, heat, not drought
Correlating each climate index with detrended yield:

| Index | Correlation with yield anomaly |
|-------|-------------------------------|
| Heatwave days | **r = −0.26** (more extreme heat → lower yield) |
| Summer mean Tmax | r = −0.02 (warmth *on average* doesn't matter) |
| Growing-season precip | r = +0.14 (weak; dry alone barely hurts) |

The three **hottest** summers (2022, 2023, 2017) all lost yield (−5, −10, −11%).
The driest years are a coin-flip (2017 bad, but 2016 and 2021 fine). So the
compound signal is really **extreme heat, amplified by concurrent drought**;
**drought alone shows almost no effect**, consistent with wine grapes being
drought-tolerant. This is a non-obvious finding in its own right.

---

## 6. Limitations

1. **Small sample.** 18 years; only 2 severe compound years. The dose-response
   mitigates this but does not remove it. No formal significance test yet.
2. **Confounding.** 2017's collapse was also driven by an **April frost**, not
   summer heat/drought. Production has many non-climate drivers (frost, vine age,
   alternate bearing, economics, disease).
3. **Grid smoothing.** ERA5's 0.25° cell is an areal average; it damps true local
   extremes, so absolute heatwave-day counts are conservative.
4. **Spatial sampling is a modelling choice.** Six wine-district points, equally
   weighted, reasonable, but not production-weighted or elevation-explicit.
5. **One region, one crop, quantity only.** No wine *quality* (where warm-dry
   years often *help*), which is the economically dominant variable in Piedmont.
6. **Threshold sensitivity.** `COMPOUND_SEVERITY_PCTL` is the single biggest lever
   on the headline; it is exposed in config and the dose-response is reported
   alongside the result.

---

## 7. Scope of this POC, and why it scales

This is a proof-of-concept, so its scope is deliberately bounded. The important
point is that **every boundary here is a *data* question, not an *engineering*
one**: the pipeline already handles the general case and was simply not fed more
than this analysis needs.

**Timeline (18 years, not 80).** The original framing mentioned an ~80-year
window, but the analysis runs **2006–2023** because that is the extent of the
**ISTAT production data**. The *production–climate* link can only be as long as
the production record, so pushing further back adds nothing to correlate against.
This is a limit of the supplied data, not of the code: the climate side is ERA5,
which reaches **1940**, and extending it is a **one-line change**
(`CLIMATE_START_YEAR` in `config.py`) plus a re-run. So an 80-year *climate-stress
trend* (how heat and drought themselves have intensified) is available on demand
as context, but it was left out here because it cannot yet be tied to production.

**Regions (Piedmont only).** Piedmont was the agreed starting point.
Adding Tuscany, Veneto, or all of Italy needs **only two inputs**, that region's
ISTAT production numbers and its province polygons (already available from the
same Eurostat NUTS source we used). No new code: the province codes,
sampling points, and thresholds are all centralised in `config.py`, and the
dashboard map already pans and zooms across the whole country, so other regions'
provinces drop straight in and shade themselves.

**In short:** the deliverable is a **working, reusable pipeline** (ISTAT to
climate indices to compound classification to interactive map). Scaling it up
(more years, more regions, more crops) is a matter of **supplying more data**, not
rebuilding anything. The Piedmont 18-year result is exactly what all of Italy over
80 years would produce, given the inputs.

---

## 8. What more could be done

- **Longer climate baseline** (ERA5 back to 1950/1940) for more robust anomaly
  percentiles, even though production only exists from 2006.
- **Better drought index**, SPI or **SPEI** (which includes evapotranspiration,
  so it captures heat-driven drying) instead of raw precipitation totals.
- **Phenology-aware windows**, stress weighted by growth stage (flowering vs
  veraison vs harvest) rather than fixed JJA / Apr–Sep blocks.
- **Growing-degree-days & spring-frost** features, to separate 2017's frost from
  its heat/drought and reduce confounding.
- **Quality alongside quantity**, sugar/acidity or vintage ratings, since the
  economic story for fine wine is often the opposite of the yield story.
- **Statistical testing**, bootstrap / permutation tests for the compound gap;
  regression with multiple predictors instead of a two-group mean comparison.
- **More regions / crops**, the pipeline is parameterised (`config.py`) to
  retarget quickly.

---

## 9. Order-invariant ("how, not when") learning, relevance & future direction

A direction worth noting: forecasting and impact analysis where **the *composition*
of conditions matters more than their temporal order or recency** ("*how* a season
unfolds" over "*when* it happened").

**Naming it precisely.** "Non-hierarchical" is most standard as *flat clustering*
(k-means, unlike agglomerative/hierarchical clustering). The property described
here, insensitivity to order/recency, is better named **permutation invariance
/ exchangeability**, realised by **set-based models** (Deep Sets, Zaheer et al.
2017) and **attention/transformers without positional encoding**, and more
broadly by **feature/configuration-based (tabular) models**. The contrast class is
**autoregressive / recency-weighted** models (ARIMA, exponential smoothing, RNNs)
where *when* and *how recently* dominate.

**How this analysis already embodies it.** Each year is treated as an
**exchangeable sample** described by a *bundle of features* (heatwave days,
growing-season rain, and their co-occurrence). We deliberately **detrend to remove
the time/recency component**, and we **never use last year's yield to predict this
year's**. So the classification is driven by *how the season is composed*
(hot-and-dry configuration), not by *when* it occurred. Note that the
**concurrent vs sequential** distinction is exactly the order question in
miniature: a *concurrent* event is **order-free** (co-occurrence), while a
*sequential* event is the case where **order carries the meaning**.

**The caveat.** Pure order-invariance is not wholly correct for viticulture. There are genuine temporal dependencies: previous-season carry-over,
the vine's physiological "memory", and, crucially, **the timing of stress
relative to growth stage** (heat at flowering ≠ heat at harvest). So *across
years* recency matters little, but *within a season* timing matters a great deal.
The interesting design question is which axis of "time" to discard and which to
keep.

**Concrete future work in this frame:**
- **Set / attention model of a season.** Encode each growing season as a *set* of
  weekly climate states and predict yield with a **permutation-invariant** model
  (Deep Sets) or self-attention. Then add positional/temporal encodings and test
  whether they improve prediction, an *empirical* answer to "does *when* add
  signal beyond *how*?" for this crop.
- **Event-typology (flat) clustering.** Run **k-means / GMM** (genuinely
  *non-hierarchical* clustering) on standardised annual climate features to
  discover compound-event **archetypes**, then relate archetypes to yield, a
  data-driven successor to our hand-built categories, and a direct use of the term
  as usually defined.
- **Baselines to beat.** Compare both against an autoregressive/recency model to
  quantify how much (or how little) chronology actually helps here.

In summary, this analysis is already a **"configuration over chronology"**
approach; the natural next step is to make that explicit and testable with
set-based or flat-clustering methods, and to measure whether adding temporal order
earns its keep.
