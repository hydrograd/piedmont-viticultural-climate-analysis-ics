# Revision notes

A short log of substantive changes made after review, so the reasoning is
traceable.

## Round 1: dashboard and finding consistency (post-review)

**Feedback.** A review noted that the graphs did not clearly match the headline
numbers, and that the map shading did not track the strong and weak years.

**Diagnosis.** Three real issues, confirmed against the data:

1. **The map was effectively static.** It shaded each province by its *absolute*
   yield on a single global colour scale. Province yields vary little year to year
   (coefficient of variation 8 to 24%), so dragging the year slider barely changed
   the map. It did not reflect the good and bad years the headline describes.
2. **The map could contradict the finding.** In the compound year 2017, tiny
   Verbano-Cusio-Ossola was +35% against its own average (shaded high) while
   Vercelli was -28%. Because small, low-weight provinces occupy equal visual
   area, a regionally weak year could look partly strong.
3. **The timeline's marked years were not the visibly lowest.** The lowest-yield
   year in the record, 2008, is classified `normal` (not a climate-stress year),
   while the compound years rank only 4th (2017) and 9th (2022) lowest. This is
   the honest result (2008, 2011, 2012 were mild, wet years, so their low yields
   were not climate-driven), but the dashboard did not say so, so it read as an
   inconsistency.

**Changes.**

- **Map now defaults to "Yield vs province average (%)"**, a diverging view
  (burgundy below average, green above), so weak years read burgundy across the
  region and the map animates meaningfully. Absolute yield and production remain
  available as options. A caption explains that small provinces are volatile and
  low-weight. (`src/production.py` adds the per-province `yield_vs_mean_pct`
  column; `app.py` selects a diverging, symmetric, zero-centred scale for it.)
- **The yield timeline gained the long-run trend line**, so the marked years are
  read against trend rather than in absolute terms.
- **The finding now reports the trend-adjusted gap** (compound years about 8
  points below trend, normal years near trend) alongside the raw comparison, and
  states plainly that climate is one driver among several, with 2008 and 2012 as
  examples of low years that were not climate-related. (`compound.headline` now
  returns the detrended-anomaly comparison.)

**Result.** The map, timeline, and headline now tell a consistent story on a
relative-to-normal basis, and the one genuine limitation (climate is not the sole
driver of yield) is stated in the interface rather than left as an apparent
contradiction.
