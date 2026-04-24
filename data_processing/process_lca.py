"""
process_lca.py — Process DOL OFLC LCA Disclosure Data into state-level aggregates.

INPUT:  Raw .xlsx files downloaded from:
        https://www.dol.gov/agencies/eta/foreign-labor/performance
        Place them in:  data/raw/lca/
        Expected filename pattern: LCA_Disclosure_Data_FY<YEAR>_Q<N>.xlsx
                                or LCA_Disclosure_Data_FY<YEAR>.xlsx

OUTPUT: data/processed/lca_by_state.csv
        Columns: fiscal_year, state_abbr, naics_2digit, naics_2digit_label,
                 num_applications, median_wage, approval_rate

USAGE:  python data_processing/process_lca.py
"""

import os
import re
import gc
import glob
import warnings
import pandas as pd

warnings.filterwarnings("ignore", message="Mean of empty slice")

# ── Config ─────────────────────────────────────────────────────────────────────
RAW_DIR      = "data/raw/lca"
OUTPUT_PATH  = "data/processed/lca_by_state.csv"
# FY2019 suffixes worksite-level columns with "_1" (one row per worksite slot).
# Newer years use unsuffixed names. Try suffixed variants first so we get the
# worksite wage when available.
WAGE_COL_OPTIONS = [
    "WAGE_RATE_OF_PAY_FROM_1", "WAGE_RATE_OF_PAY_FROM",
    "PREVAILING_WAGE_1", "PREVAILING_WAGE",
    "WAGE_RATE_FROM",
]

# NAICS 2-digit labels (most common in H-1B data)
NAICS_LABELS = {
    "51": "Information",
    "52": "Finance & Insurance",
    "54": "Professional/Scientific/Tech",
    "55": "Management of Companies",
    "61": "Educational Services",
    "62": "Health Care",
    "72": "Accommodation & Food",
    "81": "Other Services",
    "99": "Unknown",
}

# Columns we need (names differ across years — we'll try each)
COL_MAPS = {
    "case_status":   ["CASE_STATUS", "STATUS"],
    "state":         ["WORKSITE_STATE", "WORKSITE_STATE_1", "EMPLOYER_STATE", "STATE_1"],
    "zip":           ["WORKSITE_POSTAL_CODE", "WORKSITE_POSTAL_CODE_1", "EMPLOYER_POSTAL_CODE"],
    "naics":         ["NAICS_CODE", "NAICS"],
    "wage":          WAGE_COL_OPTIONS,
    "wage_unit":     ["WAGE_UNIT_OF_PAY", "WAGE_UNIT_OF_PAY_1"],
    "fiscal_year":   [],  # derived from filename
}

# Pre-compute set of all possible column names for usecols filtering
_ALL_NEEDED_COLS = set()
for _opts in COL_MAPS.values():
    for _o in _opts:
        _ALL_NEEDED_COLS.add(_o)


def find_col(df, options):
    for opt in options:
        if opt in df.columns:
            return opt
    return None


def annualize_wage(row, wage_col, unit_col):
    """Convert wage to annual if unit column is present."""
    wage = row.get(wage_col)
    if pd.isna(wage):
        return None
    unit = str(row.get(unit_col, "Year")).strip().lower()
    multipliers = {"hour": 2080, "week": 52, "bi-weekly": 26, "month": 12, "year": 1}
    for key, mult in multipliers.items():
        if key in unit:
            return wage * mult
    return wage  # fallback: assume annual


def extract_fiscal_year(filename):
    match = re.search(r"FY(\d{4})", filename, re.IGNORECASE)
    return int(match.group(1)) if match else None


VALID_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
    'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
    'VA','WA','WV','WI','WY','DC'
}

# Files above this threshold use lxml streaming instead of calamine.
# Calamine can expand a 73 MB xlsx to 671 MB+ in RAM, and its Rust OOM panic
# kills the Python process (uncatchable). Use lxml streaming for all files
# on memory-constrained systems.
_SIZE_LIMIT = 0  # 0 = always use lxml streaming


def process_file(path):
    fy = extract_fiscal_year(os.path.basename(path))
    if fy is None:
        print(f"  ⚠ Could not extract fiscal year from {path}, skipping.")
        return None

    file_size = os.path.getsize(path)
    fname = os.path.basename(path)
    print(f"  Processing FY{fy}: {fname} ({file_size // (1024*1024)} MB)", flush=True)

    if file_size > _SIZE_LIMIT:
        return _process_file_streaming(path, fy)
    return _process_file_fast(path, fy)


def _process_file_fast(path, fy):
    """Use calamine (Rust) for fast reading of files ≤ 150 MB.
    Falls back to lxml streaming if calamine OOMs."""
    try:
        raw = pd.read_excel(path, engine="calamine", dtype=str)
        raw.columns = [str(c).upper().strip() for c in raw.columns]
        keep = [c for c in raw.columns if c in _ALL_NEEDED_COLS]
        raw = raw[keep]
        print(f"    [calamine] Columns: {keep}  ({len(raw):,} rows)", flush=True)
    except Exception as e:
        if "memory allocation" in str(e).lower() or "alloc" in str(e).lower():
            print(f"    [calamine] OOM on {os.path.basename(path)}, falling back to lxml streaming…", flush=True)
            gc.collect()
            return _process_file_streaming(path, fy)
        print(f"  ✗ Failed to read {path}: {e}")
        return None

    return _filter_and_clean(raw, fy)


def _process_file_streaming(path, fy):
    """Use lxml iterparse on the xlsx XML for fast, low-memory streaming."""
    import zipfile
    from lxml import etree

    NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ROW_TAG = f"{{{NS}}}row"
    CELL_TAG = f"{{{NS}}}c"
    VAL_TAG = f"{{{NS}}}v"

    try:
        zf = zipfile.ZipFile(path, "r")
    except Exception as e:
        print(f"  ✗ Failed to open {path}: {e}")
        return None

    # ── Load shared strings table (disk-backed for low memory) ──────────────
    # Large LCA files (FY2019: 270 MB) have millions of unique shared strings.
    # Holding them all as Python str objects exhausts RAM, so we stream them
    # into a temp file and keep only (offset, length) per entry.
    import array
    import tempfile

    ss_offsets = array.array("Q")  # uint64 byte offsets into ss_file
    ss_lengths = array.array("I")  # uint32 byte lengths
    ss_file = tempfile.TemporaryFile(mode="w+b")
    if "xl/sharedStrings.xml" in zf.namelist():
        with zf.open("xl/sharedStrings.xml") as f:
            for event, elem in etree.iterparse(f, events=("end",),
                                                tag=f"{{{NS}}}si"):
                parts = []
                for t_el in elem.iter(f"{{{NS}}}t"):
                    if t_el.text:
                        parts.append(t_el.text)
                data = "".join(parts).encode("utf-8")
                ss_offsets.append(ss_file.tell())
                ss_lengths.append(len(data))
                ss_file.write(data)
                elem.clear()
                # Drop already-parsed siblings so lxml doesn't keep them all
                # attached to the root element (otherwise RAM blows up).
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
    ss_file.flush()
    print(f"    [lxml] Indexed {len(ss_offsets):,} shared strings on disk", flush=True)

    def ss_get(idx):
        if idx < 0 or idx >= len(ss_offsets):
            return None
        ss_file.seek(ss_offsets[idx])
        return ss_file.read(ss_lengths[idx]).decode("utf-8", errors="replace")

    # ── Find sheet path ─────────────────────────────────────────────────────
    sheet_path = None
    for name in ["xl/worksheets/sheet1.xml", "xl/worksheets/Sheet1.xml"]:
        if name in zf.namelist():
            sheet_path = name
            break
    if sheet_path is None:
        # Try first worksheet
        for name in zf.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                sheet_path = name
                break
    if sheet_path is None:
        print(f"  ✗ No worksheet found in {path}")
        zf.close()
        return None

    # ── Helper: column letter → 0-based index ──────────────────────────────
    def col_letter_to_idx(ref):
        col = ""
        for ch in ref:
            if ch.isalpha():
                col += ch
            else:
                break
        idx = 0
        for ch in col.upper():
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
        return idx - 1

    # ── Helper: get cell value ──────────────────────────────────────────────
    def cell_value(cell_elem):
        t = cell_elem.get("t")
        v_el = cell_elem.find(VAL_TAG)
        if v_el is None or v_el.text is None:
            return None
        if t == "s":
            idx = int(v_el.text)
            return ss_get(idx)
        return v_el.text

    # ── Stream rows ─────────────────────────────────────────────────────────
    headers = None
    col_idx = {}       # key → column letter index
    rows = []
    row_count = 0

    # Extract sheet to a temp file before parsing. zipfile's streaming reader
    # can raise OSError 22 on Windows when lxml requests large reads from a
    # 1+ GB compressed entry. Reading from a real file avoids that.
    sheet_tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
    sheet_tmp_path = sheet_tmp.name
    try:
        with zf.open(sheet_path) as src:
            while True:
                chunk = src.read(1 << 20)  # 1 MiB chunks
                if not chunk:
                    break
                sheet_tmp.write(chunk)
        sheet_tmp.close()
        print(f"    [lxml] Extracted sheet to temp ({os.path.getsize(sheet_tmp_path) // (1024*1024)} MB)", flush=True)

        with open(sheet_tmp_path, "rb") as f:
            for event, elem in etree.iterparse(f, events=("end",), tag=ROW_TAG):
                cells = elem.findall(CELL_TAG)
                cell_map = {}
                for c in cells:
                    ref = c.get("r")
                    if ref:
                        ci = col_letter_to_idx(ref)
                        cell_map[ci] = cell_value(c)

                if headers is None:
                    headers = {}
                    for ci, val in cell_map.items():
                        if val:
                            headers[ci] = str(val).upper().strip()
                    # Map our needed columns to their column indices
                    for key, names in COL_MAPS.items():
                        for name in names:
                            for ci, h in headers.items():
                                if h == name:
                                    col_idx[key] = ci
                                    break
                            if key in col_idx:
                                break
                    if "case_status" not in col_idx or "state" not in col_idx:
                        print(f"  ✗ Missing required columns in {path}")
                        zf.close()
                        ss_file.close()
                        return None
                    print(f"    [lxml] Mapped columns: {list(col_idx.keys())}", flush=True)
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
                    continue

                row_count += 1
                if row_count % 100_000 == 0:
                    print(f"    … {row_count:,} rows", flush=True)

                # Inline filter: case_status
                status = cell_map.get(col_idx["case_status"])
                if status is None or "CERTIFIED" not in status.upper():
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
                    continue

                # Inline filter: state
                state_val = cell_map.get(col_idx["state"])
                if state_val is None:
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
                    continue
                state = state_val.strip().upper()[:2]
                if state not in VALID_STATES:
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
                    continue

                naics = "99"
                if "naics" in col_idx:
                    nv = cell_map.get(col_idx["naics"])
                    if nv is not None:
                        naics = str(nv).strip()[:2]

                wage = None
                if "wage" in col_idx:
                    wv = cell_map.get(col_idx["wage"])
                    if wv is not None:
                        try:
                            wage = float(str(wv).replace(",", ""))
                            if "wage_unit" in col_idx:
                                unit_val = cell_map.get(col_idx["wage_unit"])
                                unit = str(unit_val or "Year").strip().lower()
                                for ukey, mult in [("hour", 2080), ("week", 52),
                                                    ("bi-weekly", 26), ("month", 12)]:
                                    if ukey in unit:
                                        wage *= mult
                                        break
                        except (ValueError, TypeError):
                            wage = None

                rows.append((state, naics, wage))
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
    finally:
        try:
            os.unlink(sheet_tmp_path)
        except OSError:
            pass

    zf.close()
    ss_file.close()
    print(f"    Total: {row_count:,} → {len(rows):,} certified", flush=True)

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=["state_abbr", "naics_2digit", "annual_wage"])
    df["fiscal_year"] = fy
    df["naics_2digit_label"] = df["naics_2digit"].map(NAICS_LABELS).fillna("Other")
    return df[["fiscal_year", "state_abbr", "naics_2digit",
                "naics_2digit_label", "annual_wage"]]


def _filter_and_clean(df, fy):
    """Common filter / transform logic for calamine-read DataFrames."""
    status_col = find_col(df, COL_MAPS["case_status"])
    state_col  = find_col(df, COL_MAPS["state"])
    naics_col  = find_col(df, COL_MAPS["naics"])
    wage_col   = find_col(df, COL_MAPS["wage"])
    unit_col   = find_col(df, COL_MAPS["wage_unit"])

    if status_col is None or state_col is None:
        print(f"  ✗ Missing required columns. Found: {list(df.columns[:15])}")
        return None

    df = df[df[status_col].str.upper().str.contains("CERTIFIED", na=False)]
    if df.empty:
        return None

    df["fiscal_year"] = fy
    df["state_abbr"] = df[state_col].str.strip().str.upper().str[:2]
    df = df[df["state_abbr"].isin(VALID_STATES)]

    if naics_col:
        df["naics_2digit"] = df[naics_col].astype(str).str.strip().str[:2]
    else:
        df["naics_2digit"] = "99"
    df["naics_2digit_label"] = df["naics_2digit"].map(NAICS_LABELS).fillna("Other")

    if wage_col:
        col = df[wage_col]
        if col.dtype == object:
            col = col.str.replace(",", "", regex=False)
        df[wage_col] = pd.to_numeric(col, errors="coerce")
        if unit_col:
            df["annual_wage"] = df.apply(
                lambda r: annualize_wage(r, wage_col, unit_col), axis=1
            )
        else:
            df["annual_wage"] = df[wage_col]
    else:
        df["annual_wage"] = None

    result = df[["fiscal_year", "state_abbr", "naics_2digit",
                  "naics_2digit_label", "annual_wage"]].copy()
    print(f"    → {len(result):,} certified rows", flush=True)
    return result


def aggregate(df):
    grouped = df.groupby(["fiscal_year", "state_abbr", "naics_2digit",
                           "naics_2digit_label"])
    result = grouped.agg(
        num_applications=("fiscal_year", "count"),
        median_wage=("annual_wage", "median"),
    ).reset_index()
    result["approval_rate"] = None
    return result


def main():
    from collections import defaultdict

    os.makedirs("data/processed", exist_ok=True)
    files = glob.glob(os.path.join(RAW_DIR, "*.xlsx"))

    if not files:
        print(f"No .xlsx files found in {RAW_DIR}/")
        print("Download from: https://www.dol.gov/agencies/eta/foreign-labor/performance")
        return

    # Group files by fiscal year so we aggregate per-FY (limits peak memory)
    fy_groups = defaultdict(list)
    for f in sorted(files):
        fy = extract_fiscal_year(os.path.basename(f))
        if fy:
            fy_groups[fy].append(f)

    print(f"Found {len(files)} file(s) across {len(fy_groups)} fiscal years. Processing...")

    agg_results = []
    for fy in sorted(fy_groups):
        fy_frames = []
        for f in fy_groups[fy]:
            result = process_file(f)
            if result is not None:
                fy_frames.append(result)
            gc.collect()
        if fy_frames:
            fy_combined = pd.concat(fy_frames, ignore_index=True)
            del fy_frames
            agg = aggregate(fy_combined)
            del fy_combined
            agg_results.append(agg)
            print(f"  ✓ FY{fy}: {agg['num_applications'].sum():,} applications", flush=True)
        gc.collect()

    if not agg_results:
        print("No data processed.")
        return

    final = pd.concat(agg_results, ignore_index=True)
    final.to_csv(OUTPUT_PATH, index=False)
    print(f"\n✓ Saved {len(final):,} rows → {OUTPUT_PATH}")
    print(f"  Fiscal years: {sorted(final['fiscal_year'].unique())}")
    print(f"  States: {final['state_abbr'].nunique()}")


if __name__ == "__main__":
    main()
