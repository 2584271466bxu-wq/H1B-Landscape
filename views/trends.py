"""
Approval Trends page — USCIS approval/denial rates over time.
Requires: data/processed/uscis_trends.csv  (produced by data_processing/process_uscis.py)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

DATA_PATH = "data/processed/uscis_trends.csv"

# Presidential administration bands (fiscal year boundaries, clipped to data range)
ADMINS = [
    {"label": "Trump I", "start": 2019, "end": 2020, "color": "rgba(230,159,0,0.10)"},
    {"label": "Biden",   "start": 2021, "end": 2024, "color": "rgba(0,158,115,0.10)"},
    {"label": "Trump II","start": 2025, "end": 2025, "color": "rgba(230,159,0,0.10)"},
]

COLORS = {
    "approval":  "#0072B2",
    "denial":    "#FF3366",
    "rfe":       "#E69F00",
}

# Employer name normalization — merge known variants under a canonical name
EMPLOYER_NORMALIZE = {}
_GROUPS = {
    "Amazon": ["AMAZON COM SERVICES LLC", "AMAZON.COM SERVICES LLC", "AMAZON.COM SERVICES INC",
               "AMAZON COM SERVICES INC", "AMAZON WEB SERVICES INC", "AMAZON DEVELOPMENT CENTER US INC",
               "AMAZON DEVELOPMENT CENTER U S INC", "AMAZON DATA SERVICES INC",
               "AMAZON ROBOTICS LLC", "AMAZON ADVERTISING LLC"],
    "Cognizant": ["COGNIZANT TECHNOLOGY SOLUTIONS US", "COGNIZANT TECHNOLOGY SOLUTIONS US CORP",
                  "COGNIZANT TECH SOLNS US CORP"],
    "Tata Consultancy": ["TATA CONSULTANCY SVCS LTD", "TATA CONSULTANCY SERVICES LIMITED"],
    "Infosys": ["INFOSYS LIMITED", "INFOSYS LTD"],
    "Deloitte": ["DELOITTE CONSULTING LLP", "DELOITTE & TOUCHE LLP", "DELOITTE TAX LLP",
                 "DELOITTE AND TOUCHE LLP"],
    "Ernst & Young": ["ERNST YOUNG US LLP", "ERNST & YOUNG US LLP", "ERNST AND YOUNG U S LLP"],
    "JPMorgan Chase": ["JPMORGAN CHASE CO", "JPMORGAN CHASE AND CO", "JPMORGAN CHASE & CO"],
    "Meta": ["META PLATFORMS INC", "FACEBOOK INC"],
    "Goldman Sachs": ["GOLDMAN SACHS SERVICES LLC", "GOLDMAN SACHS CO LLC",
                      "GOLDMAN SACHS AND CO LLC", "GOLDMAN SACHS BANK USA"],
    "IBM": ["IBM CORPORATION", "IBM INDIA PRIVATE LIMITED"],
    "HCL America": ["HCL AMERICA INC", "HCL GLOBAL SYSTEMS INC"],
    "Bank of America": ["BANK OF AMERICA NA", "BANK OF AMERICA N A"],
    "Citibank": ["CITIBANK N A", "CITIBANK NA"],
    "Salesforce": ["SALESFORCE COM INC", "SALESFORCE INC"],
    "Walmart": ["WAL MART ASSOCIATES INC", "WAL-MART ASSOCIATES INC"],
    "PwC": ["PRICEWATERHOUSECOOPERS ADVISORY SE", "PRICEWATERHOUSECOOPERS LLP"],
    "Fidelity": ["FIDELITY INVESTMENTS", "FIDELITY TECHNOLOGY GROUP LLC D B A FIDELITY INVESTMENTS"],
    "Capital One": ["CAPITAL ONE SERVICES LLC", "CAPITAL ONE NATIONAL ASSOCIATION"],
    "Wells Fargo": ["WELLS FARGO BANK NA", "WELLS FARGO BANK N A"],
    "General Motors": ["GENERAL MOTORS COMPANY", "GENERAL MOTORS"],
    "Larsen & Toubro": ["LARSEN AND TOUBRO INFOTECH LIMITED", "LARSEN AND TOUBRO INFOTECH LTD"],
    "LTIMindtree": ["LTIMINDTREE LIMITED", "MINDTREE LIMITED", "L T TECHNOLOGY SERVICES LTD",
                     "L T TECHNOLOGY SERVICES LIMITED"],
    "NTT Data": ["NTT DATA INC", "NTT DATA SERVICES LLC"],
    "Virtusa": ["VIRTUSA CORPORATION", "VIRTUSA CONSULTING SVCS PVT LTD"],
    "Visa": ["VISA TECHNOLOGY & OPERATIONS LLC", "VISA U S A INC"],
    "Dell": ["DELL USA L P", "DELL PRODUCTS L P"],
    "Birlasoft": ["BIRLASOFT INC", "BIRLASOFT SOLUTIONS INC"],
    "Randstad": ["RANDSTAD TECHNOLOGIES LLC", "RANDSTAD DIGITAL LLC"],
    "American Express": ["AMERICAN EXPRESS TRAVEL RELATED SERVICES COMPANY INC",
                         "AMERICAN EXPRESS TRAVEL RELATED"],
}
for canonical, variants in _GROUPS.items():
    for v in variants:
        EMPLOYER_NORMALIZE[v] = canonical


@st.cache_data
def load_data():
    if not os.path.exists(DATA_PATH):
        return None
    df = pd.read_csv(DATA_PATH)
    df["employer_name"] = df["employer_name"].replace(EMPLOYER_NORMALIZE)
    # Pre-aggregate to reduce memory: one row per (fiscal_year, employer_name)
    agg = (
        df.groupby(["fiscal_year", "employer_name"], as_index=False)
        .agg(total_approvals=("total_approvals", "sum"),
             total_denials=("total_denials", "sum"))
    )
    return agg


def render():
    st.title("Approval & Denial Trends")
    st.markdown(
        "If you made it through the lottery, congratulations — that was the hard part. "
        "But there's still one more hurdle: USCIS reviewing your petition. "
        "Approved or denied, having a petition filed already makes you one of the lucky ones. "
        "Here's how those outcomes have shifted over the years."
    )

    df = load_data()

    if df is None:
        st.warning(
            f"**Data not yet loaded.** Run `data_processing/process_uscis.py` first to generate `{DATA_PATH}`."
        )
        st.code("python data_processing/process_uscis.py", language="bash")
        _show_placeholder()
        return

    # ── Filters ─────────────────────────────────────────────────────────────────
    top_emp_names = sorted(
        df.groupby("employer_name", as_index=False)["total_approvals"]
        .sum()
        .nlargest(100, "total_approvals")["employer_name"]
        .tolist()
    )
    employers = ["All Employers"] + top_emp_names
    employer = st.selectbox("Filter by employer", employers)

    # ── Filter ───────────────────────────────────────────────────────────────────
    plot_df = df.copy()
    if employer != "All Employers":
        plot_df = plot_df[plot_df["employer_name"] == employer]

    agg = (
        plot_df.groupby("fiscal_year", as_index=False)
        .agg(
            total=("total_approvals", "sum"),
            approvals=("total_approvals", "sum"),
            denials=("total_denials", "sum"),
        )
    )
    agg["approval_rate"] = agg["approvals"] / (agg["approvals"] + agg["denials"]) * 100
    agg["denial_rate"]   = 100 - agg["approval_rate"]

    # ── Plot ─────────────────────────────────────────────────────────────────────
    fig = go.Figure()

    # Administration shading + labels
    for adm in ADMINS:
        fig.add_vrect(
            x0=adm["start"] - 0.5, x1=adm["end"] + 0.5,
            fillcolor=adm["color"], line_width=0,
        )
        fig.add_annotation(
            x=(adm["start"] + adm["end"]) / 2,
            y=103, yref="y",
            text=adm["label"],
            showarrow=False,
            font=dict(size=11, color="#555"),
        )

    fig.add_trace(go.Scatter(
        x=agg["fiscal_year"], y=agg["approval_rate"],
        mode="lines+markers", name="Approval Rate (%)",
        line=dict(color=COLORS["approval"], width=2.5),
        marker=dict(size=7),
    ))
    fig.add_trace(go.Scatter(
        x=agg["fiscal_year"], y=agg["denial_rate"],
        mode="lines+markers", name="Denial Rate (%)",
        line=dict(color=COLORS["denial"], width=2.5),
        marker=dict(size=7),
    ))

    fig.add_annotation(text="Rate (%)", xref="paper", yref="paper",
                       x=-0.06, y=1.05, showarrow=False,
                       font=dict(size=12), xanchor="left")
    fig.update_layout(
        title="H-1B Approval vs. Denial Rate by Fiscal Year",
        xaxis=dict(title="", tickangle=0),
        yaxis=dict(title="", range=[0, 105], tickangle=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=450,
        margin=dict(t=60, b=40, l=60),
    )
    st.plotly_chart(fig, width="stretch")

    # ── Top employers by petition volume ─────────────────────────────────────────
    st.subheader("Top Employers by Petition Volume")
    yr_range = st.slider(
        "Fiscal year range",
        int(df["fiscal_year"].min()), int(df["fiscal_year"].max()),
        (int(df["fiscal_year"].min()), int(df["fiscal_year"].max())),
    )
    top_emp = (
        df[df["fiscal_year"].between(*yr_range)]
        .groupby("employer_name", as_index=False)
        .agg(total=("total_approvals", "sum"))
        .nlargest(15, "total")
    )
    fig2 = go.Figure(go.Bar(
        x=top_emp["total"],
        y=top_emp["employer_name"],
        orientation="h",
        marker_color=COLORS["approval"],
    ))
    fig2.update_layout(
        xaxis=dict(title="Total Approvals", tickangle=0),
        yaxis=dict(title="", autorange="reversed", tickangle=0),
        height=420,
        margin=dict(l=200, t=30, b=40),
    )
    st.plotly_chart(fig2, width="stretch")

    # ── Employer petition trends over time ───────────────────────────────────────
    st.subheader("Employer Petition Trends Over Time")
    top_names = sorted(top_emp["employer_name"].tolist())
    selected_emps = st.multiselect(
        "Select employers to compare",
        top_names,
        default=top_names[:5],
    )
    if selected_emps:
        emp_trend = (
            df[df["employer_name"].isin(selected_emps)]
            .groupby(["fiscal_year", "employer_name"], as_index=False)
            .agg(petitions=("total_approvals", "sum"))
        )
        palette = ["#0072B2", "#E69F00", "#009E73", "#FF3366", "#56B4E9",
                    "#CC79A7", "#D55E00", "#F0E442", "#000000", "#999999",
                    "#1B9E77", "#D95F02", "#7570B3", "#E7298A", "#66A61E"]
        fig3 = go.Figure()
        for i, name in enumerate(selected_emps):
            emp_data = emp_trend[emp_trend["employer_name"] == name]
            fig3.add_trace(go.Scatter(
                x=emp_data["fiscal_year"], y=emp_data["petitions"],
                mode="lines+markers", name=name,
                line=dict(color=palette[i % len(palette)], width=2),
                marker=dict(size=5),
            ))
        fig3.update_layout(
            xaxis=dict(title="", tickangle=0, dtick=1),
            yaxis=dict(title="", tickangle=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            height=420,
            margin=dict(t=40, b=40),
        )
        fig3.add_annotation(text="Approvals", xref="paper", yref="paper",
                            x=0, y=1.02, showarrow=False,
                            font=dict(size=11), xanchor="left")
        st.plotly_chart(fig3, width="stretch")


def _show_placeholder():
    st.markdown("#### What this page will show")
    st.markdown("""
    - **Line chart** of approval/denial rates shaded by presidential administration
    - **Bar chart** of top employers by petition volume
    - Year-range slider filter
    """)
