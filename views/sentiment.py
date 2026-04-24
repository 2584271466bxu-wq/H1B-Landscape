"""
Reddit Sentiment page — VADER sentiment over time with policy annotations.
Requires: data/processed/sentiment_monthly.csv  (produced by data_processing/process_reddit.py)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import numpy as np

DATA_PATH = "data/processed/sentiment_monthly.csv"

# Key policy events to annotate on the chart
POLICY_EVENTS = [
    {"date": "2017-04", "label": "Buy American / Hire American EO", "y": 0.99, "ax": 0},
    {"date": "2019-01", "label": "H-1B selection rule proposed",   "y": 0.99, "ax": 0},
    {"date": "2020-06", "label": "COVID suspension",               "y": 0.99, "ax": -50},
    {"date": "2020-10", "label": "Wage rule (blocked)",             "y": 0.85, "ax": 0},
    {"date": "2021-02", "label": "Biden reverses Trump bans",       "y": 0.99, "ax": 50},
    {"date": "2023-01", "label": "Lottery rule (wage-based)",        "y": 0.99, "ax": 0},
    {"date": "2025-01", "label": "Trump II exec orders",             "y": 0.99, "ax": 0},
]

COLORS = {
    "sentiment":  "#0072B2",
    "volume":     "#E69F00",
    "event_line": "#FF3366",
    "pos":        "#009E73",
    "neg":        "#D55E00",
}

ANXIETY_KEYWORDS = ["RFE", "denial", "layoff", "stamping", "rejection", "H1B ban", "lottery"]


@st.cache_data
def load_data():
    if not os.path.exists(DATA_PATH):
        return None
    df = pd.read_csv(DATA_PATH, parse_dates=["month"])
    return df


def render():
    st.title("Reddit Sentiment")
    st.markdown(
        "How does community anxiety on r/h1b compare to official approval statistics? "
        "VADER compound scores range from **−1** (most negative) to **+1** (most positive)."
    )

    df = load_data()

    if df is None:
        st.warning(
            f"**Data not yet loaded.** Run `data_processing/process_reddit.py` first "
            f"to generate `{DATA_PATH}`."
        )
        st.code("python data_processing/process_reddit.py", language="bash")
        _show_placeholder()
        return

    # ── Filters ──────────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        source = st.radio("Data source", ["Posts", "Comments", "Both"], horizontal=True)
    with col2:
        layers = st.multiselect(
            "Show on chart",
            ["Monthly Sentiment", "3-Month Avg", "Post Volume"],
            default=["3-Month Avg"],
        )

    date_range = st.slider(
        "Date range",
        min_value=df["month"].min().to_pydatetime(),
        max_value=df["month"].max().to_pydatetime(),
        value=(df["month"].min().to_pydatetime(), df["month"].max().to_pydatetime()),
        format="MMM YYYY",
    )

    # ── Filter ────────────────────────────────────────────────────────────────────
    mask = (df["month"] >= date_range[0]) & (df["month"] <= date_range[1])
    if source != "Both":
        mask &= df["source"] == source.lower()
    plot_df = df[mask].copy()

    # Aggregate across sources if "Both"
    agg = (
        plot_df.groupby("month", as_index=False)
        .agg(
            compound_mean=("compound_mean", "mean"),
            post_count=("post_count", "sum"),
        )
    )
    # 3-month rolling average for readability
    agg = agg.sort_values("month")
    agg["compound_smooth"] = agg["compound_mean"].rolling(3, min_periods=1).mean()

    # ── Sentiment / Volume chart ──────────────────────────────────────────────────
    show_sentiment = "Monthly Sentiment" in layers
    show_smooth = "3-Month Avg" in layers
    show_volume = "Post Volume" in layers
    use_secondary = show_volume and (show_sentiment or show_smooth)

    fig = go.Figure()

    if show_sentiment or show_smooth:
        fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)

    if show_volume:
        fig.add_trace(go.Bar(
            x=agg["month"], y=agg["post_count"],
            name="Post Volume",
            marker_color=COLORS["volume"],
            opacity=0.3 if use_secondary else 0.8,
            yaxis="y2" if use_secondary else "y",
        ))

    if show_sentiment:
        fig.add_trace(go.Scatter(
            x=agg["month"], y=agg["compound_mean"],
            mode="lines", name="Monthly Sentiment",
            line=dict(color=COLORS["sentiment"], width=1, dash="dot"),
            opacity=0.5,
        ))

    if show_smooth:
        fig.add_trace(go.Scatter(
            x=agg["month"], y=agg["compound_smooth"],
            mode="lines", name="3-Month Avg",
            line=dict(color=COLORS["sentiment"], width=2.5),
        ))

    # Policy event annotations
    visible_events = [
        ev for ev in POLICY_EVENTS
        if date_range[0] <= pd.to_datetime(ev["date"]).to_pydatetime() <= date_range[1]
    ]
    for ev in visible_events:
        ev_date = pd.to_datetime(ev["date"])
        fig.add_shape(
            type="line", x0=ev_date.isoformat(), x1=ev_date.isoformat(),
            y0=0, y1=1, yref="paper",
            line=dict(dash="dash", color=COLORS["event_line"], width=1),
            opacity=0.5,
        )
        fig.add_annotation(
            x=ev_date.isoformat(), y=ev["y"], yref="paper",
            text=ev["label"], showarrow=True,
            arrowhead=2, arrowwidth=0.8, arrowcolor=COLORS["event_line"],
            ay=0, ax=ev["ax"],
            font=dict(size=8, color=COLORS["event_line"]),
            align="center", yanchor="bottom",
            bgcolor="rgba(255,255,255,0.8)",
        )

    # Dynamic y-axis title
    if show_sentiment or show_smooth:
        y_title = "VADER Compound"
    elif show_volume and not use_secondary:
        y_title = "Posts"
    else:
        y_title = ""

    layout_kw = dict(
        title="r/h1b Sentiment Over Time",
        xaxis=dict(title="", tickangle=0),
        yaxis=dict(title="", tickangle=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=450,
        margin=dict(t=60, b=30),
    )
    if use_secondary:
        layout_kw["yaxis2"] = dict(
            title="", overlaying="y", side="right",
            showgrid=False, tickangle=0,
        )
        fig.add_annotation(text="Posts", xref="paper", yref="paper",
                           x=1.01, y=1.02, showarrow=False,
                           font=dict(size=11), xanchor="left")
    if y_title:
        fig.add_annotation(text=y_title, xref="paper", yref="paper",
                           x=0, y=1.02, showarrow=False,
                           font=dict(size=11), xanchor="left")
    fig.update_layout(**layout_kw)
    st.plotly_chart(fig, width="stretch")

    # ── Perception gap callout ────────────────────────────────────────────────────
    st.divider()
    st.subheader("The Perception Gap")
    gap_col1, gap_col2 = st.columns(2)
    with gap_col1:
        st.metric(
            "Average USCIS Approval Rate (2019–2025)",
            "~95%",
            help="Source: USCIS H-1B Employer Data Hub",
        )
    with gap_col2:
        if len(agg) > 0:
            avg_sent = agg["compound_smooth"].mean()
            sentiment_label = "Slightly Negative" if avg_sent < 0 else "Slightly Positive"
            st.metric(
                "Average Reddit Sentiment (same period)",
                f"{avg_sent:.3f}",
                delta=sentiment_label,
                delta_color="inverse",
            )

    st.caption(
        "Even when approval rates are high, community sentiment trends negative — "
        "reflecting anxiety about RFEs, lottery uncertainty, and policy volatility."
    )

    # ── Word Cloud ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("What Drives Anxiety")
    st.markdown(
        "Words that appear disproportionately in **negative** posts "
        "(VADER ≤ −0.3), sized by distinctiveness."
    )
    neg_path = "data/processed/wordcloud_neg.csv"
    if os.path.exists(neg_path):
        from wordcloud import WordCloud

        neg_wc_df = pd.read_csv(neg_path)

        def make_wordcloud(wc_df, colormap, n=25):
            top = wc_df.head(n)
            freq = dict(zip(top["word"], top["weight"]))
            wc = WordCloud(
                width=800, height=400,
                background_color="white",
                colormap=colormap,
                max_words=n,
                prefer_horizontal=0.85,
                relative_scaling=0.5,
            ).generate_from_frequencies(freq)
            return wc.to_array()

        img_neg = make_wordcloud(neg_wc_df, "Reds")
        st.image(img_neg, use_container_width=True)
    else:
        st.info("Word cloud data not yet generated. Run the word cloud preprocessing script.")

    # ── Keyword frequency ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Anxiety Keywords Over Time")
    st.markdown(
        "Frequency of terms like *RFE*, *denial*, *layoff*, *stamping* in post titles."
    )

    kw_path = "data/processed/keyword_monthly.csv"
    if os.path.exists(kw_path):
        kw_df = pd.read_csv(kw_path, parse_dates=["month"])
        kw_cols = [c for c in kw_df.columns if c != "month"]
        selected_kws = st.multiselect("Keywords", kw_cols, default=kw_cols[:4])
        if selected_kws:
            fig3 = go.Figure()
            palette = [COLORS["sentiment"], COLORS["event_line"], COLORS["volume"],
                       COLORS["pos"], COLORS["neg"], "#CC79A7", "#000000"]
            for i, kw in enumerate(selected_kws):
                fig3.add_trace(go.Scatter(
                    x=kw_df["month"], y=kw_df[kw],
                    mode="lines", name=kw,
                    line=dict(color=palette[i % len(palette)], width=2),
                ))
            fig3.update_layout(
                xaxis=dict(title="", tickangle=0),
                yaxis=dict(title="", tickangle=0),
                height=350, margin=dict(t=20, b=40),
                hovermode="x unified",
            )
            fig3.add_annotation(text="Mentions", x=-0.04, xref="paper", y=1.0, yref="paper",
                                showarrow=False, font=dict(size=12), xanchor="right")
            st.plotly_chart(fig3, width="stretch")
    else:
        st.info("Keyword frequency data not yet generated. Run `process_reddit.py` to produce it.")


def _show_placeholder():
    st.markdown("#### What this page will show")
    st.markdown("""
    - **Sentiment time series** (VADER compound) with policy event annotations
    - **Post volume overlay** to contextualize sentiment swings
    - **Perception gap** metrics: USCIS approval rates vs. Reddit mood
    - **Keyword frequency** chart for anxiety terms (RFE, denial, layoff, stamping)
    """)
