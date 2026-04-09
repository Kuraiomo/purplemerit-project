"""
Tool 3: compare_trends
Compares pre-launch baseline period vs post-launch window for each metric.
Identifies which metrics degraded, improved, or stayed stable after launch.
Called by: Data Analyst Agent, PM Agent
"""


def compare_trends(metrics_data: dict) -> dict:
    """
    Compares baseline (pre-launch) vs launch window metrics.
    Produces a directional verdict per metric and an overall launch impact score.

    Args:
        metrics_data: Full metrics.json dict

    Returns:
        Dict with per-metric comparison + launch impact classification
    """
    launch_day = metrics_data["launch_day"]
    comparisons = {}
    degraded  = []
    improved  = []
    stable    = []

    for metric_name, metric_info in metrics_data["metrics"].items():
        values   = metric_info["values"]
        days     = sorted(values.keys(), key=lambda d: int(d.split("_")[1]))
        series   = [values[d] for d in days]
        day_nums = [int(d.split("_")[1]) for d in days]

        threshold_max = metric_info.get("threshold_max")
        threshold_min = metric_info.get("threshold_min")

        baseline_vals = [v for d, v in zip(day_nums, series) if d < launch_day]
        launch_vals   = [v for d, v in zip(day_nums, series) if d >= launch_day]

        if not baseline_vals or not launch_vals:
            continue

        baseline_avg = sum(baseline_vals) / len(baseline_vals)
        launch_avg   = sum(launch_vals)   / len(launch_vals)
        delta        = launch_avg - baseline_avg
        pct_delta    = (delta / baseline_avg) * 100 if baseline_avg != 0 else 0

        # Early window (first 3 launch days) vs late window (last 3 launch days)
        early_window = launch_vals[:3]
        late_window  = launch_vals[-3:]
        early_avg    = sum(early_window) / len(early_window)
        late_avg     = sum(late_window)  / len(late_window)
        intra_delta  = late_avg - early_avg
        intra_pct    = (intra_delta / early_avg) * 100 if early_avg != 0 else 0

        # Determine if change is good or bad based on threshold type
        if threshold_max:
            # Lower is better
            change_direction = "worsened" if delta > 0 else "improved"
            significant = abs(pct_delta) > 5
            intra_worsening = intra_delta > 0
        elif threshold_min:
            # Higher is better
            change_direction = "improved" if delta > 0 else "worsened"
            significant = abs(pct_delta) > 3
            intra_worsening = intra_delta < 0
        else:
            change_direction = "changed"
            significant = abs(pct_delta) > 5
            intra_worsening = False

        # Final verdict
        if change_direction == "worsened" and significant:
            verdict = "DEGRADED"
            degraded.append(metric_name)
        elif change_direction == "improved" and significant:
            verdict = "IMPROVED"
            improved.append(metric_name)
        else:
            verdict = "STABLE"
            stable.append(metric_name)

        comparisons[metric_name] = {
            "baseline_avg":       round(baseline_avg, 3),
            "launch_avg":         round(launch_avg, 3),
            "delta":              round(delta, 3),
            "pct_delta":          round(pct_delta, 2),
            "early_launch_avg":   round(early_avg, 3),
            "late_launch_avg":    round(late_avg, 3),
            "intra_launch_pct":   round(intra_pct, 2),
            "still_worsening":    intra_worsening,
            "verdict":            verdict,
            "unit":               metric_info["unit"],
        }

    # Launch impact score: penalise degraded, reward improved
    total = len(comparisons)
    impact_score = round(
        ((len(improved) - len(degraded)) / total) * 100, 1
    ) if total > 0 else 0

    # Classify overall launch impact
    if len(degraded) >= 5:
        launch_impact = "SEVERELY_NEGATIVE"
    elif len(degraded) >= 3:
        launch_impact = "NEGATIVE"
    elif len(degraded) >= 1:
        launch_impact = "MIXED"
    else:
        launch_impact = "POSITIVE"

    return {
        "tool":           "compare_trends",
        "launch_day":     launch_day,
        "degraded":       degraded,
        "improved":       improved,
        "stable":         stable,
        "launch_impact":  launch_impact,
        "impact_score":   impact_score,
        "comparisons":    comparisons,
    }


if __name__ == "__main__":
    import json
    with open("../data/metrics.json") as f:
        data = json.load(f)
    result = compare_trends(data)
    print(f"\n=== compare_trends output ===")
    print(f"Launch Impact: {result['launch_impact']} (score: {result['impact_score']})")
    print(f"Degraded:  {result['degraded']}")
    print(f"Improved:  {result['improved']}")
    print(f"Stable:    {result['stable']}")
    print("\nPer-metric comparison:")
    for name, info in result["comparisons"].items():
        print(f"  [{info['verdict']}] {name}: "
              f"baseline {info['baseline_avg']} → launch {info['launch_avg']} "
              f"({info['pct_delta']:+.1f}%) "
              f"{'⚠️ still worsening' if info['still_worsening'] else ''}")