"""
Mapping the H-1B Landscape: Where the Jobs Are and What People Say About Them
QMSS G5063 Data Visualization — Nicole Xu (yx3010@columbia.edu)
"""

import streamlit as st

st.set_page_config(
    page_title="H-1B Landscape",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Color palette (course palette) ────────────────────────────────────────────
COLORS = {
    "orange":   "#E69F00",
    "sky":      "#56B4E9",
    "green":    "#009E73",
    "yellow":   "#F0E442",
    "blue":     "#0072B2",   # default mark color
    "vermil":   "#D55E00",
    "pink":     "#CC79A7",
    "black":    "#000000",
    "accent":   "#FF3366",
}

# ── Sidebar navigation ─────────────────────────────────────────────────────────
st.sidebar.title("H-1B Landscape")
st.sidebar.markdown("*Mapping jobs and public discourse*")
st.sidebar.divider()

# Sidebar labels mirror the project's narrative arc:
# claim → who's eligible → who gets picked → who gets approved → what people say → method.
# Home is the landing page (the gap thesis); About sits right after so readers
# can check sources/methods early, then move into the narrative arc.
PAGES = {
    "Home":                        "overview",
    "About & Methods":             "about",
    "Where the Jobs Are":          "geography",
    "Who Gets Picked":             "lottery",
    "Approval Reality":            "trends",
    "What People Actually Say":    "sentiment",
}

# Plain-text nav: each page is a borderless full-width button. The active
# page is highlighted via Streamlit's "primary" button type (filled with the
# theme's primaryColor); inactive pages render as flat text.
st.markdown(
    """
    <style>
    /* Borderless, left-aligned, full-width sidebar nav buttons */
    section[data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        text-align: left;
        justify-content: flex-start;
        border: none;
        background: transparent;
        box-shadow: none;
        padding: 0.4rem 0.75rem;
        font-weight: 400;
        color: inherit;
    }
    section[data-testid="stSidebar"] div.stButton > button:hover {
        background: rgba(0, 114, 178, 0.08);  /* faint primary tint */
        color: inherit;
    }
    /* Active page = primary button: solid primaryColor background */
    section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: #0072B2;
        color: #FFFFFF;
        font-weight: 600;
    }
    section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover {
        background: #005d92;
        color: #FFFFFF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "page" not in st.session_state:
    st.session_state.page = next(iter(PAGES))

for label in PAGES:
    is_active = st.session_state.page == label
    if st.sidebar.button(
        label,
        key=f"nav_{label}",
        type="primary" if is_active else "secondary",
        use_container_width=True,
    ):
        st.session_state.page = label
        st.rerun()

page = st.session_state.page

st.sidebar.divider()
st.sidebar.caption("Data: DOL LCA · USCIS · Reddit r/h1b")
st.sidebar.caption("QMSS G5063 · Spring 2026")

# ── Page routing ───────────────────────────────────────────────────────────────
import importlib
module = importlib.import_module(f"views.{PAGES[page]}")
module.render()
