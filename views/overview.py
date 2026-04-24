"""Overview / landing page — hero + one-sentence thesis."""
import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go


SENTIMENT_PATH = "data/processed/sentiment_monthly.csv"
USCIS_PATH = "data/processed/uscis_trends.csv"

COLORS = {
    "approval": "#0072B2",   # course blue
    "sentiment": "#D55E00",  # vermillion (colorblind-safe contrast)
    "muted":     "#888888",
}


@st.cache_data
def _load_hero_data():
    """Load the two series for the hero gap chart, returning (df, error_msg)."""
    if not (os.path.exists(SENTIMENT_PATH) and os.path.exists(USCIS_PATH)):
        return None, "Hero chart will appear once the data pipelines have been run."

    sent = pd.read_csv(SENTIMENT_PATH, parse_dates=["month"])
    sent["fiscal_year"] = sent["month"].dt.year
    sent = (
        sent.groupby("fiscal_year", as_index=False)
        .agg(compound=("compound_mean", "mean"))
    )

    uscis = pd.read_csv(USCIS_PATH)
    uscis = (
        uscis.groupby("fiscal_year", as_index=False)
        .agg(approvals=("total_approvals", "sum"),
             denials=("total_denials", "sum"))
    )
    uscis["approval_rate"] = uscis["approvals"] / (uscis["approvals"] + uscis["denials"]) * 100

    df = uscis.merge(sent, on="fiscal_year", how="inner").sort_values("fiscal_year")
    return df, None


def _hero_gap_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["approval_rate"],
        name="USCIS approval rate (%)",
        mode="lines+markers",
        line=dict(color=COLORS["approval"], width=3),
        marker=dict(size=8),
        hovertemplate="FY%{x}<br>Approval rate: %{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["compound"],
        name="r/h1b avg sentiment (VADER)",
        mode="lines+markers",
        line=dict(color=COLORS["sentiment"], width=3, dash="dot"),
        marker=dict(size=8),
        yaxis="y2",
        hovertemplate="FY%{x}<br>Avg sentiment: %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="Approvals stay high. Sentiment doesn't follow.",
        xaxis=dict(title="", dtick=1, tickformat="d"),
        yaxis=dict(
            title=dict(text="Approval rate (%)", standoff=10),
            range=[60, 105], color=COLORS["approval"], ticksuffix="%",
        ),
        yaxis2=dict(
            title=dict(text="Avg sentiment (−1 → +1)", standoff=10),
            range=[-1, 1], overlaying="y", side="right",
            color=COLORS["sentiment"], showgrid=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.05,
                    xanchor="center", x=0.5),
        hovermode="x unified",
        height=380,
        margin=dict(t=70, b=60, l=90, r=90),
    )
    # Force horizontal axis-title text (Plotly rotates y-axis titles 90° by default).
    fig.update_yaxes(title_standoff=10)
    fig.layout.yaxis.title.font = dict(size=12)
    fig.layout.yaxis2.title.font = dict(size=12)
    # Move y-axis titles to top of each axis, rendered horizontally via annotations.
    fig.layout.yaxis.title.text = ""
    fig.layout.yaxis2.title.text = ""
    fig.add_annotation(
        text="Approval rate (%)", xref="paper", yref="paper",
        x=0, y=1.02, showarrow=False, xanchor="left",
        font=dict(size=12, color=COLORS["approval"]),
    )
    fig.add_annotation(
        text="Avg sentiment (−1 → +1)", xref="paper", yref="paper",
        x=1, y=1.02, showarrow=False, xanchor="right",
        font=dict(size=12, color=COLORS["sentiment"]),
    )
    return fig


def render():
    # ── Hero / framing ────────────────────────────────────────────────
    st.markdown(
        "<h1 style='margin-bottom:0.25rem'>Mapping the H-1B Landscape</h1>"
        "<p style='font-size:1.35rem; line-height:1.45; color:#444; margin-top:0;'>"
        "H-1B approval rates have stayed above 90% for years — "
        "yet on r/h1b, anxiety keeps rising. <b>This project is about that gap.</b>"
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "The H-1B is the United States' main work visa for skilled, college-educated "
        "foreign professionals — concentrated in tech, finance, healthcare, and academia. "
        "Each year USCIS receives far more registrations than the **85,000-petition cap**, "
        "so a lottery decides who even gets to file. The program has been at the center "
        "of policy debates across the last three administrations, which makes it a useful "
        "lens on how official statistics and lived experience can drift apart."
    )
    st.markdown("")

    # ── Hero chart ─────────────────────────────────────────────────────
    df, err = _load_hero_data()
    if df is not None and not df.empty:
        st.plotly_chart(_hero_gap_chart(df), width="stretch")
        st.caption(
            "Two series, same fiscal years. The blue line (USCIS approval rate) sits near "
            "the top of its axis. The orange line (average VADER sentiment on r/h1b) drifts "
            "toward zero — the language people use about the program does not match the "
            "approval statistics."
        )
    else:
        st.info(err or "Run the data pipelines to render the hero chart.")

    st.divider()

    # ── Headline numbers ────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("USCIS petitions (FY2021)", "~488,000",
                  help="Source: USCIS H-1B Employer Data Hub")
    with col2:
        st.metric("Reddit posts analyzed", "60,037",
                  help="r/h1b archive 2015–2026, via Arctic Shift")
    with col3:
        st.metric("Years covered", "2019–2025",
                  help="DOL & USCIS fiscal-year data")

    st.divider()

    # ── Reading guide (clickable chapter shortcuts) ─────────────────────
    st.markdown("### How to read this story")
    st.markdown("Jump to any chapter, or follow them in order:")

    chapters = [
        ("About & Methods",
         "Data sources, definitions, methodology, and libraries."),
        ("Where the Jobs Are",
         "The geography of demand — which states soak up most petitions."),
        ("Who Gets Picked",
         "The lottery: most prospective workers never even file a petition."),
        ("Approval Reality",
         "Once filed, denials are rare and trending lower."),
        ("What People Actually Say",
         "Yet sentiment on r/h1b tells a very different story."),
    ]
    for label, description in chapters:
        btn_col, desc_col = st.columns([1, 3])
        with btn_col:
            if st.button(label, key=f"jump_{label}", use_container_width=True):
                st.session_state.page = label
                st.rerun()
        with desc_col:
            st.markdown(
                f"<div style='padding-top:0.45rem; color:#444;'>{description}</div>",
                unsafe_allow_html=True,
            )

