"""
Tool 5: cluster_feedback_themes
Groups feedback entries by topic/theme using keyword matching.
No LLM — pure rule-based clustering. Identifies dominant complaint themes.
Called by: Sentiment Agent, Marketing Agent
"""

from collections import defaultdict

# Theme definitions: theme_name -> keywords to match (case-insensitive)
THEME_KEYWORDS = {
    "payment_failure": [
        "payment failed", "failed", "failure", "transaction failed",
        "not go through", "declined", "rejected", "fail"
    ],
    "duplicate_charge": [
        "duplicate", "charged twice", "double charge", "charged anyway",
        "deducted", "charged", "refund", "financial"
    ],
    "app_crash": [
        "crash", "crashed", "crashing", "force close", "closed", "restart"
    ],
    "performance_slow": [
        "slow", "slower", "loading", "took a while", "timeout",
        "timed out", "latency", "lag", "overloaded", "forever"
    ],
    "support_unresponsive": [
        "support ticket", "no response", "unresolved", "support",
        "no resolution", "no reply"
    ],
    "trust_churn_risk": [
        "cancel", "cancelling", "unacceptable", "trust", "legal",
        "leaving", "stopped using", "rolled back", "roll it back"
    ],
    "positive_experience": [
        "great", "excellent", "love", "fast", "easy", "seamless",
        "works perfectly", "clean", "intuitive", "best", "slick"
    ],
    "setup_funnel_issue": [
        "setup", "funnel", "onboarding", "step", "complete", "finish",
        "couldn't complete", "keeps timing"
    ],
}


def cluster_feedback_themes(feedback_list: list) -> dict:
    """
    Assigns each feedback entry to one or more themes based on keyword matching.
    Returns theme counts, representative quotes per theme, and dominant themes.

    Args:
        feedback_list: List of feedback dicts from feedback.json

    Returns:
        Dict with theme clusters, counts, and dominant issue ranking
    """
    theme_entries   = defaultdict(list)
    theme_day_dist  = defaultdict(lambda: defaultdict(int))
    unmatched       = []

    for entry in feedback_list:
        text_lower  = entry["text"].lower()
        matched_themes = []

        for theme, keywords in THEME_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                matched_themes.append(theme)
                theme_entries[theme].append({
                    "id":      entry["id"],
                    "day":     entry["day"],
                    "rating":  entry["rating"],
                    "text":    entry["text"],
                })
                theme_day_dist[theme][entry["day"]] += 1

        if not matched_themes:
            unmatched.append(entry["id"])

    # Build summary per theme
    theme_summary = {}
    for theme, entries in theme_entries.items():
        avg_rating  = sum(e["rating"] for e in entries) / len(entries)
        days_active = sorted(set(e["day"] for e in entries))

        # Pick most representative quote (lowest rating = most critical)
        worst_entry = min(entries, key=lambda x: x["rating"])

        theme_summary[theme] = {
            "count":              len(entries),
            "avg_rating":         round(avg_rating, 2),
            "days_active":        days_active,
            "first_seen_day":     min(days_active),
            "day_distribution":   dict(sorted(theme_day_dist[theme].items())),
            "representative_quote": worst_entry["text"],
            "is_negative_theme":  theme != "positive_experience",
        }

    # Rank themes by count (negative only)
    negative_themes = {
        k: v for k, v in theme_summary.items()
        if v["is_negative_theme"]
    }
    ranked_issues = sorted(
        negative_themes.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )

    # Dominant theme (most mentioned negative issue)
    dominant_issue = ranked_issues[0][0] if ranked_issues else None

    # Escalation flag: any theme appearing in 3+ consecutive days
    escalating_themes = []
    for theme, info in theme_summary.items():
        days = info["days_active"]
        if len(days) >= 3:
            consecutive = all(
                days[i+1] - days[i] == 1
                for i in range(len(days) - 1)
            )
            if consecutive and info["is_negative_theme"]:
                escalating_themes.append(theme)

    return {
        "tool":               "cluster_feedback_themes",
        "total_entries":      len(feedback_list),
        "unmatched_ids":      unmatched,
        "dominant_issue":     dominant_issue,
        "escalating_themes":  escalating_themes,
        "ranked_issues":      [
            {"theme": k, "count": v["count"], "avg_rating": v["avg_rating"]}
            for k, v in ranked_issues
        ],
        "theme_details":      theme_summary,
    }


if __name__ == "__main__":
    import json
    with open("../data/feedback.json") as f:
        feedback = json.load(f)
    result = cluster_feedback_themes(feedback)
    print(f"\n=== cluster_feedback_themes output ===")
    print(f"Dominant issue: {result['dominant_issue']}")
    print(f"Escalating themes: {result['escalating_themes']}")
    print(f"\nRanked issues:")
    for item in result["ranked_issues"]:
        print(f"  {item['count']:>3}x  [{item['avg_rating']:.1f}★]  {item['theme']}")
    print(f"\nTheme details:")
    for theme, info in result["theme_details"].items():
        print(f"  {theme}: first seen day {info['first_seen_day']}, "
              f"days active {info['days_active']}")
        print(f"    Quote: \"{info['representative_quote'][:70]}...\"")