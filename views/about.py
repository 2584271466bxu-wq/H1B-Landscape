"""About page."""
import os
import streamlit as st


# Project root → Image/ directory (sits next to app.py)
_IMAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "Image")


# Process-book images: numbered 1.png … 5.png in /Image/, displayed in order.
PROCESS_BOOK_IMAGES = ["1.png", "2.png", "3.png", "4.png", "5.png"]


def render():
    st.title("About This Project")

    st.markdown("""
    **Mapping the H-1B Landscape: Where the Jobs Are and What People Say About Them**

    *QMSS G5063 Data Visualization · Columbia University · Spring 2026*
    *Nicole Xu — yx3010@columbia.edu*
    """)

    st.divider()

    st.subheader("Research Questions")
    st.markdown("""
    1. How do H-1B job opportunities distribute across states, and how have they shifted over time?
    2. How have approval and denial rates changed across presidential administrations?
    3. If denial rates remain statistically low, why does online sentiment reflect persistent anxiety?
       **That gap is the central finding.**
    """)

    st.subheader("Data Sources")
    st.markdown("""
    | Source | Description | Link |
    |--------|-------------|------|
    | DOL OFLC LCA Disclosure Data | Every Labor Condition Application, FY 2019–2025 | [dol.gov](https://www.dol.gov/agencies/eta/foreign-labor/performance) |
    | USCIS H-1B Employer Data Hub | Adjudication outcomes by employer and fiscal year | [uscis.gov](https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub) |
    | USCIS H-1B Lottery Statistics | Registration and selection counts, FY 2020–2025 | [uscis.gov](https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-1b-specialty-occupations-and-fashion-models/h-1b-electronic-registration-process) |
    | BLS Local Area Unemployment Statistics (LAUS), Table 1 | Civilian labor force by state, **March 2026** (seasonally adjusted) — used as the denominator for *petitions per 100k workforce* | [bls.gov/news.release/laus.t01.htm](https://www.bls.gov/news.release/laus.t01.htm) |
    | Reddit r/h1b via Arctic Shift | 60k posts + ~1M comments, 2015–2026 | [arctic-shift.photon-reddit.com](https://arctic-shift.photon-reddit.com/) |
    """)

    st.subheader("Methods")
    st.markdown("""
    - **Geospatial**: DOL worksite locations aggregated to state level, rendered as Plotly choropleth maps.
    - **Text Analysis**: VADER (Valence Aware Dictionary and sEntiment Reasoner) applied to Reddit
      post titles and comment bodies. Monthly aggregates smoothed with a 3-month rolling average.
    - **Keyword Tracking**: Regex-based frequency counts for anxiety terms (RFE, denial, layoff,
      stamping, rejection) in post titles.
    """)

    st.subheader("Libraries")
    st.code(
        "pandas · plotly · streamlit · vaderSentiment · wordcloud · openpyxl",
        language="text",
    )

    st.subheader("Design Notes")
    st.markdown(
        """
        - **Color palette** is drawn from the Okabe–Ito set
          (`#0072B2`, `#D55E00`, `#009E73`, `#E69F00`, …), which is
          **colorblind-safe** under deuteranopia, protanopia, and tritanopia simulation.
        - **Theme** is applied app-wide via
          [`.streamlit/config.toml`](https://docs.streamlit.io/library/advanced-features/theming),
          so background, text, and primary color are consistent across every page.
        - **Caching** — every data loader is decorated with `@st.cache_data` so
          re-running widgets does not re-read the CSVs.
        - **Narrative arc** — sidebar pages are ordered
          *Overview → Where the Jobs Are → Who Gets Picked → Approval Reality → What People Say → About*,
          mirroring the project's thesis rather than the data sources.
        """
    )

    st.divider()

    # ── Process Book ─────────────────────────────────────────────────────
    st.subheader("Process Book")
    st.markdown(
        "Early sketches of how the dashboard was imagined to read — rough layouts "
        "of each page before any code was written, mapping out where the charts, "
        "text, and navigation would sit."
    )

    for fname in PROCESS_BOOK_IMAGES:
        img_path = os.path.join(_IMAGE_DIR, fname)
        if os.path.exists(img_path):
            st.image(img_path, use_container_width=True)
        else:
            st.caption(f"_(missing image: `Image/{fname}`)_")
