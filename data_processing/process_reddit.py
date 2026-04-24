"""
process_reddit.py — VADER sentiment analysis on r/h1b Reddit data.

INPUT:  C:\\Academic\\QMSS_26Spring\\Data_Vis\\Xu_Nicole\\Final\\data\\r_h1b_posts.jsonl
        C:\\Academic\\QMSS_26Spring\\Data_Vis\\Xu_Nicole\\Final\\data\\r_h1b_comments.jsonl
        (paths configured below — update if needed)

OUTPUT: data/processed/sentiment_monthly.csv
        Columns: month, source, compound_mean, pos_mean, neg_mean, neu_mean, post_count

        data/processed/keyword_monthly.csv
        Columns: month, rfe, denial, layoff, stamping, rejection, lottery, h1b_ban

NOTES:  - Posts file (~162 MB): uses title + selftext
        - Comments file (~972 MB): streamed in chunks; default samples 20% to keep runtime < 5 min
        - Set SAMPLE_COMMENTS = 1.0 to process all comments (may take 30+ min)

USAGE:  python data_processing/process_reddit.py
"""

import os
import json
import random
from datetime import datetime, timezone
from collections import defaultdict

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ── Config ─────────────────────────────────────────────────────────────────────
POSTS_PATH    = r"C:\Academic\QMSS_26Spring\Data_Vis\Xu_Nicole\Final\data\r_h1b_posts.jsonl"
COMMENTS_PATH = r"C:\Academic\QMSS_26Spring\Data_Vis\Xu_Nicole\Final\data\r_h1b_comments.jsonl"

OUT_SENTIMENT = "data/processed/sentiment_monthly.csv"
OUT_KEYWORDS  = "data/processed/keyword_monthly.csv"

SAMPLE_COMMENTS = 0.20   # fraction of comments to process (1.0 = all)
RANDOM_SEED     = 42

# Anxiety keywords to track (case-insensitive)
KEYWORDS = {
    "rfe":        r"\brfe\b",
    "denial":     r"\bdenial\b|\bdenied\b",
    "layoff":     r"\blayoff\b|\blaid off\b",
    "stamping":   r"\bstamping\b|\bvisa stamp",
    "rejection":  r"\brejection\b|\brejected\b",
    "lottery":    r"\blottery\b",
    "h1b_ban":    r"\bban\b.*h.?1.?b|h.?1.?b.*\bban\b",
}

random.seed(RANDOM_SEED)
analyzer = SentimentIntensityAnalyzer()


# ── Helpers ────────────────────────────────────────────────────────────────────

def utc_to_month(ts):
    """Convert Unix UTC timestamp to 'YYYY-MM' string."""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m")
    except (ValueError, TypeError, OSError):
        return None


def score_text(text):
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if text in ("[deleted]", "[removed]", ""):
        return None
    return analyzer.polarity_scores(text)


def keyword_hits(text):
    """Return dict of keyword → 1/0 hit for a piece of text."""
    import re
    if not text or not isinstance(text, str):
        return {k: 0 for k in KEYWORDS}
    text_lower = text.lower()
    return {k: int(bool(re.search(pat, text_lower))) for k, pat in KEYWORDS.items()}


# ── Process posts ──────────────────────────────────────────────────────────────

def process_posts():
    print("Processing posts...")
    monthly_scores = defaultdict(list)   # month → [compound, ...]
    monthly_full   = defaultdict(list)   # month → [{compound, pos, neg, neu}]
    monthly_kw     = defaultdict(lambda: defaultdict(int))  # month → {keyword: count}

    with open(POSTS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                post = json.loads(line)
            except json.JSONDecodeError:
                continue

            month = utc_to_month(post.get("created_utc"))
            if not month:
                continue

            title    = post.get("title", "")
            selftext = post.get("selftext", "")
            text     = f"{title} {selftext}".strip()

            scores = score_text(text)
            if scores:
                monthly_full[month].append(scores)

            # Keywords on title only (cleaner signal)
            kw = keyword_hits(title)
            for k, v in kw.items():
                monthly_kw[month][k] += v

            if (i + 1) % 10000 == 0:
                print(f"  Posts: {i+1:,}")

    print(f"  ✓ Posts done. Months with data: {len(monthly_full)}")
    return monthly_full, monthly_kw


# ── Process comments ───────────────────────────────────────────────────────────

def process_comments():
    print(f"Processing comments (sampling {SAMPLE_COMMENTS*100:.0f}%)...")
    monthly_full = defaultdict(list)

    with open(COMMENTS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if random.random() > SAMPLE_COMMENTS:
                continue
            try:
                comment = json.loads(line)
            except json.JSONDecodeError:
                continue

            month = utc_to_month(comment.get("created_utc"))
            if not month:
                continue

            scores = score_text(comment.get("body", ""))
            if scores:
                monthly_full[month].append(scores)

            if (i + 1) % 100000 == 0:
                print(f"  Comments scanned: {i+1:,}")

    print(f"  ✓ Comments done. Months with data: {len(monthly_full)}")
    return monthly_full


# ── Aggregate ──────────────────────────────────────────────────────────────────

def agg_monthly(monthly_full, source_label):
    rows = []
    for month, scores_list in sorted(monthly_full.items()):
        if not scores_list:
            continue
        rows.append({
            "month":        month,
            "source":       source_label,
            "compound_mean": sum(s["compound"] for s in scores_list) / len(scores_list),
            "pos_mean":      sum(s["pos"]      for s in scores_list) / len(scores_list),
            "neg_mean":      sum(s["neg"]      for s in scores_list) / len(scores_list),
            "neu_mean":      sum(s["neu"]      for s in scores_list) / len(scores_list),
            "post_count":    len(scores_list),
        })
    return pd.DataFrame(rows)


def agg_keywords(monthly_kw):
    rows = []
    for month, kw_counts in sorted(monthly_kw.items()):
        row = {"month": month}
        row.update(kw_counts)
        rows.append(row)
    df = pd.DataFrame(rows).fillna(0)
    for k in KEYWORDS:
        if k not in df.columns:
            df[k] = 0
    return df[["month"] + list(KEYWORDS.keys())]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    os.makedirs("data/processed", exist_ok=True)

    # Check files exist
    for path, name in [(POSTS_PATH, "posts"), (COMMENTS_PATH, "comments")]:
        if not os.path.exists(path):
            print(f"⚠ {name} file not found: {path}")
            print("  Update POSTS_PATH / COMMENTS_PATH at the top of this script.")
            if name == "posts":
                return

    # Posts
    posts_monthly, kw_monthly = process_posts()
    posts_df = agg_monthly(posts_monthly, "posts")

    # Comments (optional — skip if file missing)
    if os.path.exists(COMMENTS_PATH):
        comments_monthly = process_comments()
        comments_df = agg_monthly(comments_monthly, "comments")
        sentiment_df = pd.concat([posts_df, comments_df], ignore_index=True)
    else:
        print("Comments file not found — proceeding with posts only.")
        sentiment_df = posts_df

    sentiment_df["month"] = pd.to_datetime(sentiment_df["month"])
    sentiment_df = sentiment_df.sort_values(["month", "source"]).reset_index(drop=True)
    sentiment_df.to_csv(OUT_SENTIMENT, index=False)
    print(f"\n✓ Saved sentiment → {OUT_SENTIMENT}  ({len(sentiment_df):,} rows)")

    # Keywords
    kw_df = agg_keywords(kw_monthly)
    kw_df["month"] = pd.to_datetime(kw_df["month"])
    kw_df = kw_df.sort_values("month").reset_index(drop=True)
    kw_df.to_csv(OUT_KEYWORDS, index=False)
    print(f"✓ Saved keywords  → {OUT_KEYWORDS}  ({len(kw_df):,} rows)")

    # Quick summary
    print("\nSentiment summary (posts):")
    print(posts_df.describe(include="all").loc[["mean", "min", "max"], ["compound_mean", "post_count"]])


if __name__ == "__main__":
    main()
