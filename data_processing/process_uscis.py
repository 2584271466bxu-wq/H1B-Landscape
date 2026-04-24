"""
process_uscis.py — Process USCIS H-1B Employer Data Hub files into trend data.

INPUT:  Raw .csv files downloaded from:
        https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub
        Place them in:  data/raw/uscis/

OUTPUT: data/processed/uscis_trends.csv

USAGE:  python data_processing/process_uscis.py
"""

import os
import re
import glob
import pandas as pd

RAW_DIR     = "data/raw/uscis"
OUTPUT_PATH = "data/processed/uscis_trends.csv"

# Column name variants across USCIS export versions
COL_MAPS = {
    "employer":           ["Employer", "EMPLOYER", "Petitioner Name", "PETITIONER_NAME",
                           "Employer (Petitioner) Name"],
    "fiscal_year":        ["Fiscal Year", "FISCAL_YEAR", "FY"],
    "initial_approval":   ["Initial Approval", "Initial Approvals", "INITIAL_APPROVAL"],
    "initial_denial":     ["Initial Denial", "Initial Denials", "INITIAL_DENIAL"],
    "continuing_approval":["Continuing Approval", "Continuing Approvals", "CONTINUING_APPROVAL"],
    "continuing_denial":  ["Continuing Denial", "Continuing Denials", "CONTINUING_DENIAL"],
}

# FY2024+ new format: approvals/denials split into subcategories
# We sum all approval subcategories → total_approvals, all denial subcategories → total_denials
NEW_FORMAT_APPROVAL_COLS = [
    "New Employment Approval",
    "Continuation Approval",
    "Change with Same Employer Approval",
    "New Concurrent Approval",
    "Change of Employer Approval",
    "Amended Approval",
]
NEW_FORMAT_DENIAL_COLS = [
    "New Employment Denial",
    "Continuation Denial",
    "Change with Same Employer Denial",
    "New Concurrent Denial",
    "Change of Employer Denial",
    "Amended Denial",
]


def find_col(df, options):
    for opt in options:
        if opt in df.columns:
            return opt
    return None


def extract_fiscal_year_from_filename(filename):
    match = re.search(r"(\d{4})", filename)
    return int(match.group(1)) if match else None


def read_csv_flexible(path):
    """Try multiple encodings and separators to read the CSV."""
    # List of (encoding, separator) combos to try
    attempts = [
        ("utf-8", ","),
        ("utf-8", "\t"),
        ("utf-16", None),      # utf-16 auto-detects tab vs comma
        ("utf-16-le", None),
        ("latin-1", ","),
        ("latin-1", "\t"),
    ]
    for enc, sep in attempts:
        try:
            kwargs = {"encoding": enc, "low_memory": False}
            if sep:
                kwargs["sep"] = sep
            df = pd.read_csv(path, **kwargs)
            # Quick sanity check: should have more than 1 column
            if len(df.columns) > 1:
                return df
        except Exception:
            continue

    # Last resort: try reading as Excel (some USCIS "csv" exports are actually xlsx)
    try:
        df = pd.read_excel(path)
        if len(df.columns) > 1:
            return df
    except Exception:
        pass

    return None


def process_file(path):
    print(f"  Processing: {os.path.basename(path)}")

    df = read_csv_flexible(path)
    if df is None:
        print(f"  ✗ Could not read {path} with any encoding. Skipping.")
        return None

    # Clean column names (strip whitespace, BOM characters)
    df.columns = [c.strip().strip("\ufeff") for c in df.columns]

    print(f"    Columns found: {list(df.columns[:8])}")

    employer_col  = find_col(df, COL_MAPS["employer"])
    fy_col        = find_col(df, COL_MAPS["fiscal_year"])

    if employer_col is None:
        print(f"  ✗ Could not find employer column. Found: {list(df.columns)}")
        return None

    out = pd.DataFrame()
    out["employer_name"] = df[employer_col].astype(str).str.strip().str.upper()

    # Fiscal year — from column or filename
    if fy_col:
        out["fiscal_year"] = pd.to_numeric(df[fy_col], errors="coerce")
    else:
        fy = extract_fiscal_year_from_filename(os.path.basename(path))
        out["fiscal_year"] = fy

    # ── Detect format: new (FY2024+) vs. legacy ───────────────────────────────
    is_new_format = "New Employment Approval" in df.columns

    if is_new_format:
        print(f"    → Detected NEW format (FY2024+ subcategories)")

        def _sum_cols(df, col_list):
            """Sum numeric columns that exist, returning 0 for missing ones."""
            total = pd.Series(0, index=df.index)
            for c in col_list:
                if c in df.columns:
                    total += pd.to_numeric(
                        df[c].astype(str).str.replace(",", "").str.strip(),
                        errors="coerce"
                    ).fillna(0)
            return total.astype(int)

        out["total_approvals"] = _sum_cols(df, NEW_FORMAT_APPROVAL_COLS)
        out["total_denials"]   = _sum_cols(df, NEW_FORMAT_DENIAL_COLS)

        # For compatibility, map "New Employment" → initial, "Continuation" → continuing
        out["initial_approvals"]    = _sum_cols(df, ["New Employment Approval"])
        out["initial_denials"]      = _sum_cols(df, ["New Employment Denial"])
        out["continuing_approvals"] = _sum_cols(df, ["Continuation Approval"])
        out["continuing_denials"]   = _sum_cols(df, ["Continuation Denial"])

    else:
        # Legacy format (FY2019–2023)
        ia_col = find_col(df, COL_MAPS["initial_approval"])
        id_col = find_col(df, COL_MAPS["initial_denial"])
        ca_col = find_col(df, COL_MAPS["continuing_approval"])
        cd_col = find_col(df, COL_MAPS["continuing_denial"])

        for dest, col in [
            ("initial_approvals",    ia_col),
            ("initial_denials",      id_col),
            ("continuing_approvals", ca_col),
            ("continuing_denials",   cd_col),
        ]:
            if col:
                out[dest] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", "").str.strip(),
                    errors="coerce"
                ).fillna(0).astype(int)
            else:
                out[dest] = 0

        out["total_approvals"] = out["initial_approvals"] + out["continuing_approvals"]
        out["total_denials"]   = out["initial_denials"]   + out["continuing_denials"]

    print(f"    Rows: {len(out):,} | FY: {out['fiscal_year'].dropna().unique()}")
    print(f"    Total approvals: {out['total_approvals'].sum():,} | Total denials: {out['total_denials'].sum():,}")
    return out[[
        "fiscal_year", "employer_name",
        "initial_approvals", "initial_denials",
        "continuing_approvals", "continuing_denials",
        "total_approvals", "total_denials",
    ]]


def main():
    os.makedirs("data/processed", exist_ok=True)
    files = glob.glob(os.path.join(RAW_DIR, "*.csv"))

    if not files:
        print(f"No .csv files found in {RAW_DIR}/")
        print("Download from: https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub")
        return

    print(f"Found {len(files)} file(s). Processing...")
    frames = []
    for f in sorted(files):
        result = process_file(f)
        if result is not None:
            frames.append(result)

    if not frames:
        print("No data processed.")
        return

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["fiscal_year"])
    combined["fiscal_year"] = combined["fiscal_year"].astype(int)
    combined.to_csv(OUTPUT_PATH, index=False)

    print(f"\n✓ Saved {len(combined):,} rows → {OUTPUT_PATH}")
    print(f"  Fiscal years: {sorted(combined['fiscal_year'].unique())}")
    print(f"  Unique employers: {combined['employer_name'].nunique():,}")

    # Quick summary
    summary = (
        combined.groupby("fiscal_year")[["total_approvals", "total_denials"]]
        .sum()
        .assign(approval_rate=lambda d: d["total_approvals"] / (d["total_approvals"] + d["total_denials"]) * 100)
    )
    print("\nApproval rate by year:")
    print(summary.round(1).to_string())


if __name__ == "__main__":
    main()
