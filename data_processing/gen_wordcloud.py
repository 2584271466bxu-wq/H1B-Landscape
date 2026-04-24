"""Generate word frequency CSVs for positive/negative word clouds."""
import json, re, os
from collections import Counter
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import pandas as pd

STOPWORDS = set(
    "i me my myself we our ours ourselves you your yours yourself yourselves "
    "he him his himself she her hers herself it its itself they them their "
    "theirs themselves what which who whom this that these those am is are was "
    "were be been being have has had having do does did doing a an the and but "
    "if or because as until while of at by for with about against between "
    "through during before after above below to from up down in out on off "
    "over under again further then once here there when where why how all both "
    "each few more most other some such no nor not only own same so than too "
    "very can will just don should now would could one get like also go going "
    "got know think said see want need even really well much still back lot "
    "new made time work good people make any help may two try take every find "
    "been way thing say post comment deleted removed reply many first year "
    "also right us used use please thanks thank hello hey http https www com "
    "org net html amp".split()
)
STOPWORDS |= {"h1b", "h1", "visa", "h4", "h1b1", "ead", "green", "card", "anyone", "someone"}

POSTS_PATH = "data/r_h1b_posts.jsonl"
OUT_DIR = "data/processed"

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    analyzer = SentimentIntensityAnalyzer()
    pos_words = Counter()
    neg_words = Counter()
    n_pos = n_neg = 0
    word_re = re.compile(r"[a-z]{3,}")

    with open(POSTS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                post = json.loads(line)
            except Exception:
                continue
            title = post.get("title", "") or ""
            selftext = post.get("selftext", "") or ""
            text = f"{title} {selftext}".strip()
            if not text or text in ("[deleted]", "[removed]"):
                continue
            score = analyzer.polarity_scores(text)
            words = [w for w in word_re.findall(text.lower())
                     if w not in STOPWORDS and len(w) < 20]
            if score["compound"] >= 0.05:
                pos_words.update(words)
                n_pos += 1
            elif score["compound"] <= -0.05:
                neg_words.update(words)
                n_neg += 1
            if (i + 1) % 10000 == 0:
                print(f"  {i + 1:,} posts...")

    print(f"Positive posts: {n_pos:,}, Negative posts: {n_neg:,}")
    pd.DataFrame(pos_words.most_common(100), columns=["word", "count"]).to_csv(
        f"{OUT_DIR}/wordcloud_positive.csv", index=False)
    pd.DataFrame(neg_words.most_common(100), columns=["word", "count"]).to_csv(
        f"{OUT_DIR}/wordcloud_negative.csv", index=False)
    print("Saved wordcloud CSVs")

if __name__ == "__main__":
    main()
