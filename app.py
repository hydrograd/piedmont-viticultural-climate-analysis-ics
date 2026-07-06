"""Streamlit dashboard: Piedmont viticultural climate analysis.

A map-led layout: an animated province choropleth (production or yield, by year),
the compound-event comparison, a yield timeline coloured by climate category, and
a per-year event ribbon. Reads the processed CSVs and the province GeoJSON; if the
compound analysis has not been generated yet it falls back to a production-only
view.

Run:  streamlit run app.py
"""
from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from src import compound as compound_mod

# --- palette & type --------------------------------------------------------
BG = "#181016"
PANEL = "#221A20"
CREAM = "#ECE4DA"
MUTED = "#A89AA0"
CHAMPAGNE = "#C2A878"
FONT = "Roboto"
WINE_SCALE = ["#E7DDD0", "#D3B9AE", "#B98E8C", "#9C6370", "#7A4256", "#5A2C3E"]
# Diverging scale for the yield-anomaly view: below average (burgundy) through
# neutral (cream) to above average (green).
DIVERGING = ["#7A2E3B", "#B07A82", "#E7DDD0", "#8FB0A0", "#3B6E5A"]
CATEGORY_COLORS = {
    "normal": "#5E5860", "heat_only": "#B0764C", "drought_only": "#C2A878",
    "concurrent": "#7A4256", "sequential": "#5B5470",
}
CATEGORY_HELP = {
    "normal": "neither extreme heat nor drought",
    "heat_only": "hottest-quartile summer, normal rainfall",
    "drought_only": "driest-quartile growing season, normal heat",
    "concurrent": "extreme heat and drought overlapping in a month",
    "sequential": "extreme heat and drought in different months, not overlapping",
}
METRICS = {
    "yield_vs_mean_pct": "Yield vs province average (%)",
    "yield_per_ha": "Yield (quintals / ha)",
    "production": "Production (quintals)",
}

st.set_page_config(page_title="Piedmont Viticultural Climate Analysis", layout="wide")

# Apply Roboto to the Streamlit chrome and the custom HTML blocks.
st.markdown(
    "<style>@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&display=swap');"
    "html, body, .stApp, [class*='css'], [data-testid='stMarkdownContainer'], "
    "button, input, select { font-family: 'Roboto', sans-serif !important; }</style>",
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    prov = pd.read_csv(config.PRODUCTION_BY_PROVINCE_CSV)
    comp = pd.read_csv(config.COMPOUND_CSV) if config.COMPOUND_CSV.exists() else None
    geo = json.load(open(config.PIEDMONT_GEOJSON))
    return prov, comp, geo


prov, comp, geo = load_data()

st.markdown(
    f"<h2 style='color:{CREAM};margin-bottom:0;font-weight:500'>Piedmont Viticultural Climate Analysis</h2>"
    f"<p style='color:{MUTED};margin-top:4px'>How heatwaves and rainfall deficits, alone and "
    f"as compound events, affect wine-grape production in Piedmont, Italy.</p>",
    unsafe_allow_html=True,
)

# --- headline comparison and finding ---------------------------------------
if comp is not None:
    h = compound_mod.headline(comp)
    k1, k2, k3 = st.columns(3)
    k1.metric("Compound-event years", h["n_compound"],
              help="Years in both the hottest and driest quartile: severe concurrent heat plus drought.")
    k2.metric("Normal years", h["n_normal"],
              help="Years with neither extreme heat nor drought; the comparison group.")
    if h["pct_difference"] == h["pct_difference"]:
        k3.metric("Mean yield: compound vs normal", f"{h['pct_difference']:+.1f}%",
                  help="Difference in mean yield (quintals per hectare) between compound and normal years.")
        direction = "lower" if h["pct_difference"] < 0 else "higher"
        yrs = ", ".join(str(y) for y in h["compound_years"])
        st.markdown(
            f"<div style='background:{PANEL};border-left:3px solid {CATEGORY_COLORS['concurrent']};"
            f"border-radius:6px;padding:12px 16px;color:{CREAM}'>"
            f"In severe compound heat-and-drought years (<b>{yrs}</b>), Piedmont grape yield was "
            f"<b>{abs(h['pct_difference']):.1f}% {direction}</b> than in normal years "
            f"({h['mean_yield_compound']:.0f} vs {h['mean_yield_normal']:.0f} quintals per hectare). "
            f"Adjusting for the long-run decline in vineyard area, compound years sat about "
            f"<b>{abs(h['anom_gap_pts']):.0f} points below trend</b>, while normal years were "
            f"close to trend on average.</div>",
            unsafe_allow_html=True,
        )
    st.caption("Yield = grape production ÷ vineyard area. 1 quintal = 100 kg. A compound event "
               "is a year in the top quartile for heatwave days and the bottom quartile for "
               "growing-season rainfall. Climate is one driver among several: some low-yield "
               "years (for example 2008 and 2012) were mild and wet, so those losses were not "
               "climate-related. The dotted line on the timeline is the long-run trend.")

st.write("")
left, right = st.columns([3, 2], gap="large")

# --- province choropleth ---------------------------------------------------
with left:
    metric = st.radio("Shade the map by", list(METRICS), horizontal=True,
                      format_func=lambda m: METRICS[m])
    dfm = prov.sort_values("year")

    is_anom = metric == "yield_vs_mean_pct"
    if is_anom:
        # Symmetric, diverging scale centred on 0, clipped to the 95th percentile
        # so one volatile small province does not dominate the range.
        rng = float(dfm[metric].abs().quantile(0.95))
        scale, range_color, midpoint = DIVERGING, (-rng, rng), 0
    else:
        scale = WINE_SCALE
        range_color = (dfm[metric].min(), dfm[metric].quantile(0.98))
        midpoint = None

    fig = px.choropleth_map(
        dfm, geojson=geo, locations="region_code", featureidkey="properties.NUTS_ID",
        color=metric, animation_frame="year",
        color_continuous_scale=scale, range_color=range_color,
        color_continuous_midpoint=midpoint,
        map_style="carto-darkmatter", zoom=6.7, center={"lat": 44.9, "lon": 8.0},
        opacity=0.85, hover_name="region_name",
        labels={metric: METRICS[metric], "year": "Year"},
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0), height=460,
        paper_bgcolor=BG, font_color=CREAM, font_family=FONT,
        coloraxis_colorbar=dict(title=dict(text=METRICS[metric], side="right"), thickness=12),
    )
    if fig.layout.updatemenus:
        fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 700
    st.plotly_chart(fig, use_container_width=True)
    if is_anom:
        st.caption("Each province is shaded by its yield relative to its own 2006 to 2023 "
                   "average: burgundy is a below-average year, green is above. Weaker years "
                   "read burgundy across the region. Small provinces such as Verbano are "
                   "volatile and carry little of the regional total, so an occasional bright "
                   "province in an otherwise weak year is expected. Turin is absent from the "
                   "ISTAT extract and is left unshaded.")
    else:
        st.caption("Each province is shaded by its absolute value for the selected year; "
                   "darker means higher. Note that province yields differ from the regional "
                   "figure in the headline, which is the area-weighted total. Turin is absent "
                   "from the ISTAT extract and is left unshaded.")

# --- compound timeline + ribbon -------------------------------------------
with right:
    if comp is not None:
        st.markdown(f"<p style='color:{CREAM};margin-bottom:2px;font-weight:500'>Yield over time</p>"
                    f"<p style='color:{MUTED};margin-top:0;font-size:13px'>each point coloured by that "
                    f"year's climate category; dotted line is the long-run trend</p>",
                    unsafe_allow_html=True)
        t = go.Figure()
        t.add_scatter(x=comp["year"], y=comp["yield_trend"], mode="lines", name="trend",
                      line=dict(color="#6E6168", width=1, dash="dot"), hoverinfo="skip",
                      showlegend=False)
        t.add_scatter(x=comp["year"], y=comp["yield_per_ha"], mode="lines",
                      line=dict(color=MUTED, width=1.5), hoverinfo="skip", showlegend=False)
        for cat, col in CATEGORY_COLORS.items():
            s = comp[comp["category"] == cat]
            if len(s):
                t.add_scatter(
                    x=s["year"], y=s["yield_per_ha"], mode="markers",
                    name=f"{cat.replace('_', ' ')}: {CATEGORY_HELP[cat]}",
                    marker=dict(size=13, color=col, line=dict(color=BG, width=1)),
                    hovertemplate="%{x}: %{y:.1f} q/ha<extra>" + cat.replace("_", " ") + "</extra>")
        t.update_layout(
            height=320, margin=dict(l=0, r=0, t=6, b=0),
            paper_bgcolor=BG, plot_bgcolor=BG, font_color=CREAM, font_family=FONT,
            legend=dict(orientation="h", y=-0.28, x=0, font=dict(size=10)),
            xaxis=dict(title="Year", gridcolor="#362C33"),
            yaxis=dict(title="Yield (quintals / ha)", gridcolor="#362C33"))
        st.plotly_chart(t, use_container_width=True)

        st.markdown(f"<p style='color:{CREAM};margin:6px 0 2px;font-weight:500'>Compound-event ribbon</p>"
                    f"<p style='color:{MUTED};margin-top:0;font-size:13px'>one cell per year, "
                    f"{int(comp.year.min())} (left) → {int(comp.year.max())} (right)</p>",
                    unsafe_allow_html=True)
        ribbon = " ".join(
            f"<span title='{r.year}: {r.category}' style='display:inline-block;width:5.1%;"
            f"height:18px;background:{CATEGORY_COLORS[r.category]};border-radius:2px'></span>"
            for _, r in comp.iterrows()
        )
        st.markdown(f"<div>{ribbon}</div>", unsafe_allow_html=True)
        legend = "".join(
            f"<span style='display:inline-flex;align-items:center;gap:5px;margin-right:12px'>"
            f"<span style='width:11px;height:11px;background:{c};border-radius:2px;display:inline-block'></span>"
            f"<span style='color:{MUTED};font-size:12px'>{k.replace('_',' ')}</span></span>"
            for k, c in CATEGORY_COLORS.items()
        )
        st.markdown(f"<div style='margin-top:8px'>{legend}</div>", unsafe_allow_html=True)

with st.expander("What the categories mean"):
    st.markdown("\n".join(f"- **{k.replace('_',' ')}**: {v}" for k, v in CATEGORY_HELP.items()))

with st.expander("Underlying data"):
    st.dataframe(comp if comp is not None else prov, use_container_width=True)

with st.expander("About this proof-of-concept and how it scales"):
    st.markdown(
        "This is a proof-of-concept demonstrating a **reusable pipeline**: "
        "ISTAT production, climate indices, compound classification, interactive map. "
        "Its scope is deliberate, and every boundary is a **data** question, not an "
        "engineering one.\n\n"
        "- **Timeline (2006 to 2023).** The window is set by the ISTAT production record, "
        "not the pipeline. The climate side (ERA5) reaches back to 1940; extending it is a "
        "one-line config change, so an ~80-year climate-stress trend is available on demand.\n"
        "- **Region (Piedmont).** Adding Tuscany, Veneto, or all of Italy needs only that "
        "region's production numbers and its province polygons. No new code, the map already "
        "pans across the country and other provinces shade themselves.\n\n"
        "In short: what you see for Piedmont over 18 years is what you would see for all of "
        "Italy over 80, given the inputs. Scaling up is a matter of supplying more data."
    )
