"""
Geography page — choropleth maps of H-1B distribution by state.
Requires: data/processed/lca_by_state.csv  (produced by data_processing/process_lca.py)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import os

DATA_PATH = "data/processed/lca_by_state.csv"
LABOR_FORCE_PATH = "data/processed/state_labor_force.csv"

# Course color scale anchored to blue (#0072B2)
COLOR_SCALE = [
    [0.0,  "#f7fbff"],
    [0.25, "#9ecae1"],
    [0.5,  "#4393c3"],
    [0.75, "#0072B2"],
    [1.0,  "#08306b"],
]


@st.cache_data
def load_data():
    if not os.path.exists(DATA_PATH):
        return None
    return pd.read_csv(DATA_PATH)


@st.cache_data
def load_labor_force():
    """BLS LAUS state-level civilian labor force (most recent month).
    Used as a fixed denominator for the per-100k-workforce metric."""
    if not os.path.exists(LABOR_FORCE_PATH):
        return None
    return pd.read_csv(LABOR_FORCE_PATH)


def render():
    st.title("Where the Jobs Are")
    st.markdown(
        "H-1B demand is concentrated in a handful of "
        "tech and finance hubs — California, Texas, New York, New Jersey, and Washington "
        "absorb most of the petitions every year. Use the filters to pivot by year, "
        "metric, and industry."
    )

    df = load_data()

    if df is None:
        st.warning(
            "**Data not yet loaded.** Run `data_processing/process_lca.py` first to generate "
            f"`{DATA_PATH}`."
        )
        st.code("python data_processing/process_lca.py", language="bash")
        _show_placeholder()
        return

    # ── Filters ────────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    years = sorted(df["fiscal_year"].unique(), reverse=True)
    with col1:
        year = st.selectbox("Fiscal Year", years, index=0)

    metrics = {
        "Number of Applications": "num_applications",
        "Petitions per 100k workforce": "petitions_per_100k",
        "Median Wage (USD)": "median_wage",
    }
    with col2:
        metric_label = st.selectbox("Show metric", list(metrics.keys()))

    industries = ["All Industries"] + sorted(df["naics_2digit_label"].dropna().unique().tolist())
    with col3:
        industry = st.selectbox("Industry", industries)

    # ── Filter data ────────────────────────────────────────────────────────────
    filtered = df[df["fiscal_year"] == year].copy()
    if industry != "All Industries":
        filtered = filtered[filtered["naics_2digit_label"] == industry]

    metric_col = metrics[metric_label]

    # Aggregate if multiple industries per state
    agg_funcs = {
        "num_applications":     "sum",
        "median_wage":          "median",
        "petitions_per_100k":   "sum",   # built from num_applications below
    }
    state_df = (
        filtered.groupby("state_abbr", as_index=False)
        .agg(num_applications=("num_applications", "sum"),
             median_wage=("median_wage", "median"))
    )

    # Normalize to per-100k labor force when requested
    lf = load_labor_force()
    if metric_col == "petitions_per_100k":
        if lf is None:
            st.error(
                "`data/processed/state_labor_force.csv` is missing — cannot "
                "compute the per-100k-workforce metric."
            )
            return
        state_df = state_df.merge(
            lf[["state_abbr", "labor_force"]], on="state_abbr", how="left"
        )
        state_df["petitions_per_100k"] = (
            state_df["num_applications"] / state_df["labor_force"] * 100_000
        )

    # ── Choropleth ─────────────────────────────────────────────────────────────
    fig = px.choropleth(
        state_df,
        locations="state_abbr",
        locationmode="USA-states",
        color=metric_col,
        scope="usa",
        color_continuous_scale=COLOR_SCALE,
        labels={metric_col: metric_label},
        title=f"{metric_label} by State — FY {year}" + (f" ({industry})" if industry != "All Industries" else ""),
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        coloraxis_colorbar=dict(title=metric_label),
        geo=dict(bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig, width="stretch")
    if metric_col == "petitions_per_100k":
        st.caption(
            "Petitions normalized by each state's civilian labor force "
            "(BLS Local Area Unemployment Statistics, **March 2026**, seasonally adjusted). "
            "Per-100k rates surface states that are *intensively* H-1B-driven — "
            "e.g., NJ, MA, WA — which raw counts hide behind sheer size."
        )
    # ── Top states table ───────────────────────────────────────────────────────
    st.subheader(f"Top 10 States — FY {year}")
    top = state_df.nlargest(10, metric_col)[["state_abbr", metric_col]].reset_index(drop=True)
    if metric_col == "petitions_per_100k":
        top[metric_col] = top[metric_col].round(1)

    # Find dominant industry per state (from year-filtered data, ignoring industry filter)
    year_df = df[df["fiscal_year"] == year]
    dominant = (
        year_df.groupby(["state_abbr", "naics_2digit_label"], as_index=False)["num_applications"]
        .sum()
        .sort_values("num_applications", ascending=False)
        .drop_duplicates("state_abbr")
        .rename(columns={"naics_2digit_label": "dominant_industry"})
        [["state_abbr", "dominant_industry"]]
    )
    top = top.merge(dominant, on="state_abbr", how="left")

    top.index = top.index + 1
    top.columns = ["State", metric_label, "Dominant Industry"]
    st.dataframe(top, use_container_width=True)


def _show_placeholder():
    st.markdown("#### What this page will show")
    st.markdown("""
    - **Choropleth map** of H-1B applications / wages / approval rates by state
    - Filters for fiscal year and NAICS industry
    - Top-10 states table
    """)
