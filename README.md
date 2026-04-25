# Mapping the H-1B Landscape

**QMSS G5063 Data Visualization · Columbia University · Spring 2026**
Nicole Xu — yx3010@columbia.edu

**Live demo:** [h1b-landscape.streamlit.app](https://h1b-landscape.streamlit.app/)

An interactive Streamlit dashboard that contrasts the *official* picture of
the H-1B program (high approval rates, broad geographic spread) with the
*lived* experience captured in r/h1b discussions — surfacing the gap between
administrative data and public sentiment.

---

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The processed CSVs the app needs (`data/processed/`) are committed, so it
works out of the box — no data download required.

---

## Project Structure

```
.
├── app.py                          # Streamlit entry point (sidebar router)
├── requirements.txt
├── .streamlit/config.toml          # Custom theme (Okabe–Ito palette)
├── views/                          # One module per sidebar page
│   ├── overview.py                 # Home — thesis + hero gap chart
│   ├── geography.py                # Choropleth maps
│   ├── lottery.py                  # Registration vs. selection
│   ├── trends.py                   # Approval / denial time series
│   ├── sentiment.py                # Reddit VADER sentiment
│   └── about.py                    # Methods, data sources, process book
├── data_processing/                # Raw → processed CSV pipelines
├── Image/                          # Process-book sketches (shown on About page)
└── data/
    ├── raw/                        # DOL & USCIS source files
    └── processed/                  # Small CSVs the app reads
```

---

## Data Sources

| Source | Used for |
|---|---|
| [DOL OFLC LCA Disclosure Data](https://www.dol.gov/agencies/eta/foreign-labor/performance) | Geography of H-1B job postings |
| [USCIS H-1B Employer Data Hub](https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub) | Approval / denial outcomes |
| [USCIS H-1B Lottery Statistics](https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-1b-specialty-occupations-and-fashion-models/h-1b-electronic-registration-process) | Registration vs. selection |
| [BLS LAUS, Table 1](https://www.bls.gov/news.release/laus.t01.htm) | Workforce normalization (March 2026) |
| Reddit r/h1b via [Arctic Shift](https://arctic-shift.photon-reddit.com/) | Sentiment & keyword analysis |

The raw DOL `.xlsx` files (~3 GB) and Reddit JSONL dumps (~1 GB) are too
large for GitHub. To re-run the pipelines yourself, grab them from the
mirror below and drop them into `data/raw/` and `data/`:

**[Raw data mirror (Google Drive)](https://drive.google.com/drive/folders/1l-YFCmTn7_xzbzCda0mB7YcOnJOtxG1G?usp=sharing)**

Then regenerate the processed CSVs:

```bash
python data_processing/process_lca.py
python data_processing/process_uscis.py
python data_processing/process_reddit.py
```
