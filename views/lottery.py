"""
H-1B Lottery page — registration vs selection statistics.
Requires: data/processed/h1b_lottery.csv
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

DATA_PATH = "data/processed/h1b_lottery.csv"

COLORS = {
    "registered": "#56B4E9",
    "selected":   "#2CA02C",
    "not_sel":    "#B0B0B0",
    "rate_line":  "#000000",
}


@st.cache_data
def load_data():
    path = os.path.join(os.path.dirname(__file__), "..", DATA_PATH)
    df = pd.read_csv(path)
    df["not_selected"] = df["registrations"] - df["selected"]
    df["selection_rate"] = (df["selected"] / df["registrations"] * 100).round(1)
    return df


def render():
    st.title("The H-1B Lottery")
    st.markdown(
        "Every spring, hundreds of thousands of prospective H-1B workers register "
        "for a chance to file a petition. Most **never get selected**."
    )

    df = load_data()
    if df.empty:
        st.error("Lottery data not found.")
        return

    # ── Key metrics ────────────────────────────────────────────────────────
    latest = df.iloc[-1]
    worst = df.loc[df["selection_rate"].idxmin()]

    c1, c2, c3 = st.columns(3)
    c1.metric(
        f"FY{int(latest['fiscal_year'])} Registrations",
        f"{int(latest['registrations']):,}",
    )
    c2.metric(
        f"FY{int(latest['fiscal_year'])} Selected",
        f"{int(latest['selected']):,}",
    )
    c3.metric(
        "Lowest Selection Rate",
        f"{worst['selection_rate']:.1f}%",
        help=f"FY{int(worst['fiscal_year'])}",
    )

    st.divider()

    # ── Chart 1: Registrations vs Selected (stacked bar) ──────────────────
    st.subheader("Who Gets a Chance to File?")

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df["fiscal_year"],
        y=df["selected"],
        name="Selected",
        marker_color=COLORS["selected"],
        text=[f"{v:,.0f}" for v in df["selected"]],
        textposition="inside",
        textfont=dict(color="white", size=11),
    ))

    fig.add_trace(go.Bar(
        x=df["fiscal_year"],
        y=df["not_selected"],
        name="Not Selected",
        marker_color=COLORS["not_sel"],
        text=[f"{v:,.0f}" for v in df["not_selected"]],
        textposition="inside",
        textfont=dict(color="white", size=11),
    ))

    # Selection rate as annotations above the line to avoid overlap with bar text
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"],
        y=df["selection_rate"],
        name="Selection Rate",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color=COLORS["rate_line"], width=3),
        marker=dict(size=8),
    ))

    for _, row in df.iterrows():
        fig.add_annotation(
            x=row["fiscal_year"],
            y=row["selection_rate"] + 6,
            yref="y2",
            text=f"{row['selection_rate']:.0f}%",
            showarrow=False,
            font=dict(size=12, color=COLORS["rate_line"]),
        )

    # Cap line (no label)
    fig.add_hline(
        y=85000, line_dash="dot", line_color="gray", line_width=1,
    )

    fig.update_layout(
        barmode="stack",
        yaxis=dict(title="Number of Registrations", tickformat=","),
        yaxis2=dict(
            title="",
            overlaying="y",
            side="right",
            range=[0, 100],
            showgrid=False,
            ticksuffix="%",
        ),
        xaxis=dict(
            title="",
            dtick=1,
            tickformat="d",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        margin=dict(t=60, b=40),
        height=500,
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── Callout: the human cost ───────────────────────────────────────────
    peak = df.loc[df["not_selected"].idxmax()]
    st.info(
        f"**In FY{int(peak['fiscal_year'])}, {int(peak['not_selected']):,} registrants "
        f"were not selected** — that's {100 - peak['selection_rate']:.0f}% of all applicants "
        f"who never even got the chance to file a petition."
    )

    # ── Chart 2: Selection rate over time ─────────────────────────────────
    st.subheader("Selection Rate Over Time")

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["fiscal_year"],
        y=df["selection_rate"],
        mode="lines+markers",
        line=dict(color=COLORS["rate_line"], width=3),
        marker=dict(size=10, color=COLORS["rate_line"]),
        text=[f"{v:.1f}%" for v in df["selection_rate"]],
        textposition="top center",
        textfont=dict(size=13),
        hovertemplate="FY%{x}: %{y:.1f}%<extra></extra>",
    ))

    # Shade electronic vs paper era
    fig2.add_vrect(
        x0=2019.5, x1=2020.5,
        fillcolor="rgba(200,200,200,0.15)", line_width=0,
    )
    fig2.add_annotation(
        x=2020, y=5,
        text="Paper petitions",
        showarrow=False,
        font=dict(size=10, color="gray"),
    )

    fig2.update_layout(
        yaxis=dict(title="Selection Rate (%)", range=[0, 75], ticksuffix="%"),
        xaxis=dict(title="", dtick=1, tickformat="d"),
        height=350,
        margin=dict(t=30, b=40),
    )

    st.plotly_chart(fig2, use_container_width=True)

    # ── Context / explainer ───────────────────────────────────────────────
    st.subheader("What Changed?")

    st.markdown("""
| Year | Event |
|------|-------|
| **FY2020** | Last year of paper-based petitions — employers filed full I-129 packets |
| **FY2021** | USCIS launched **electronic registration** ($10/registration), lowering the barrier to enter the lottery |
| **FY2023** | Registrations nearly **tripled** as employers and staffing firms submitted duplicate registrations for the same worker |
| **FY2025** | USCIS implemented **beneficiary-centric selection** — one registration per unique worker regardless of how many employers sponsor them, cutting fraud |
""")

    st.caption(
        "Source: USCIS H-1B Electronic Registration Data & press releases. "
        "Selected counts reflect initial selection rounds. "
        "The statutory annual cap is 85,000 (65,000 regular + 20,000 advanced degree). "
        "USCIS over-selects because not all selected registrants file petitions."
    )
