"""
Tool 4: sentiment_summarizer
Uses VADER (rule-based, no LLM) to score each feedback entry
and produce a distribution summary with top negative/positive quotes.
Called by: Sentiment Agent
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


def sentiment_summarizer(feedback_list: list) -> dict:
    """
    Runs VADER sentiment analysis on all feedback entries.
    Returns score distribution, trend over time, and representative quotes.

    Args:
        feedback_list: List of feedback dicts from feedback.json

    Returns:
        Dict with sentiment distribution, scores, trend, and top quotes
    """
    analyzer = SentimentIntensityAnalyzer()
    scored   = []

    for entry in feedback_list:
        scores = analyzer.polarity_scores(entry["text"])
        compound = scores["compound"]

        # VADER compound: >= 0.05 positive, <= -0.05 negative, else neutral
        if compound >= 0.05:
            vader_label = "positive"
        elif compound <= -0.05:
            vader_label = "negative"
        else:
            vader_label = "neutral"

        scored.append({
            "id":           entry["id"],
            "day":          entry["day"],
            "original_rating": entry["rating"],
            "text":         entry["text"],
            "compound":     round(compound, 4),
            "pos":          round(scores["pos"], 4),
            "neu":          round(scores["neu"], 4),
            "neg":          round(scores["neg"], 4),
            "vader_label":  vader_label,
        })

    # Distribution
    total     = len(scored)
    pos_count = sum(1 for s in scored if s["vader_label"] == "positive")
    neg_count = sum(1 for s in scored if s["vader_label"] == "negative")
    neu_count = sum(1 for s in scored if s["vader_label"] == "neutral")
    avg_compound = round(sum(s["compound"] for s in scored) / total, 4)

    # Sentiment trend by day
    days = sorted(set(s["day"] for s in scored))
    daily_sentiment = {}
    for day in days:
        day_entries = [s for s in scored if s["day"] == day]
        day_avg = sum(s["compound"] for s in day_entries) / len(day_entries)
        daily_sentiment[f"day_{day}"] = round(day_avg, 4)

    # Top 3 most negative and most positive entries
    sorted_by_compound = sorted(scored, key=lambda x: x["compound"])
    top_negative = [
        {"day": s["day"], "text": s["text"], "score": s["compound"]}
        for s in sorted_by_compound[:3]
    ]
    top_positive = [
        {"day": s["day"], "text": s["text"], "score": s["compound"]}
        for s in sorted_by_compound[-3:][::-1]
    ]

    # Overall sentiment verdict
    neg_ratio = neg_count / total
    if avg_compound <= -0.3 or neg_ratio >= 0.5:
        verdict = "STRONGLY_NEGATIVE"
    elif avg_compound <= -0.1 or neg_ratio >= 0.35:
        verdict = "NEGATIVE"
    elif avg_compound >= 0.3:
        verdict = "POSITIVE"
    elif avg_compound >= 0.1:
        verdict = "SLIGHTLY_POSITIVE"
    else:
        verdict = "MIXED"

    return {
        "tool":            "sentiment_summarizer",
        "total_entries":   total,
        "distribution": {
            "positive":    pos_count,
            "neutral":     neu_count,
            "negative":    neg_count,
            "pos_pct":     round(pos_count / total * 100, 1),
            "neu_pct":     round(neu_count / total * 100, 1),
            "neg_pct":     round(neg_count / total * 100, 1),
        },
        "avg_compound_score": avg_compound,
        "verdict":            verdict,
        "daily_sentiment":    daily_sentiment,
        "top_negative_quotes": top_negative,
        "top_positive_quotes": top_positive,
        "all_scored":          scored,
    }


if __name__ == "__main__":
    import json
    with open("../data/feedback.json") as f:
        feedback = json.load(f)
    result = sentiment_summarizer(feedback)
    print(f"\n=== sentiment_summarizer output ===")
    print(f"Verdict: {result['verdict']}")
    print(f"Distribution: {result['distribution']}")
    print(f"Avg compound score: {result['avg_compound_score']}")
    print(f"\nSentiment trend by day:")
    for day, score in result["daily_sentiment"].items():
        bar = "█" * int(abs(score) * 20)
        sign = "+" if score > 0 else "-"
        print(f"  {day}: {sign}{abs(score):.4f} {bar}")
    print(f"\nTop negative:")
    for q in result["top_negative_quotes"]:
        print(f"  [day {q['day']}] ({q['score']:.3f}) {q['text'][:80]}...")