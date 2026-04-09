"""
Tool 1: aggregate_metrics
Computes per-metric statistics: rolling average, day-over-day delta,
total change since launch, and threshold breach status.
Called by: Data Analyst Agent
"""

from typing import Any


def aggregate_metrics(metrics_data: dict) -> dict:
    """
    Aggregates raw time-series metrics into statistical summaries.

    Args:
        metrics_data: Full metrics.json dict

    Returns:
        Dict with per-metric aggregation + overall health summary
    """
    launch_day = metrics_data["launch_day"]
    results = {}

    for metric_name, metric_info in metrics_data["metrics"].items():
        values = metric_info["values"]
        days = sorted(values.keys(), key=lambda d: int(d.split("_")[1]))
        series = [values[d] for d in days]
        day_nums = [int(d.split("_")[1]) for d in days]

        # Split baseline vs launch
        baseline_vals = [v for d, v in zip(day_nums, series) if d < launch_day]
        launch_vals   = [v for d, v in zip(day_nums, series) if d >= launch_day]

        baseline_avg = round(sum(baseline_vals) / len(baseline_vals), 3) if baseline_vals else None
        launch_avg   = round(sum(launch_vals)   / len(launch_vals),   3) if launch_vals   else None

        # Day-over-day deltas
        dod_deltas = [
            round(series[i] - series[i - 1], 3)
            for i in range(1, len(series))
        ]

        # Total change from launch day to last day
        launch_day_val = values.get(f"day_{launch_day}")
        last_val       = series[-1]
        total_change   = round(last_val - launch_day_val, 3) if launch_day_val else None
        pct_change     = round((total_change / launch_day_val) * 100, 2) if launch_day_val else None

        # Threshold breach check
        threshold_max = metric_info.get("threshold_max")
        threshold_min = metric_info.get("threshold_min")
        breach_days   = []

        for d, v in zip(day_nums, series):
            if threshold_max is not None and v > threshold_max:
                breach_days.append(d)
            if threshold_min is not None and v < threshold_min:
                breach_days.append(d)

        breached       = len(breach_days) > 0
        first_breach   = min(breach_days) if breach_days else None

        # Trend direction over last 3 days
        last_3 = series[-3:]
        if last_3[-1] > last_3[0]:
            trend = "increasing"
        elif last_3[-1] < last_3[0]:
            trend = "decreasing"
        else:
            trend = "stable"

        results[metric_name] = {
            "unit":           metric_info["unit"],
            "description":    metric_info["description"],
            "baseline_avg":   baseline_avg,
            "launch_avg":     launch_avg,
            "latest_value":   last_val,
            "total_change_since_launch": total_change,
            "pct_change_since_launch":   pct_change,
            "dod_deltas":     dod_deltas,
            "trend_last_3d":  trend,
            "threshold_max":  threshold_max,
            "threshold_min":  threshold_min,
            "breached":       breached,
            "first_breach_day": first_breach,
            "breach_days":    breach_days,
        }

    # Overall health score: % of metrics NOT breached
    total    = len(results)
    breached_count = sum(1 for v in results.values() if v["breached"])
    healthy_count  = total - breached_count
    health_score   = round((healthy_count / total) * 100, 1)

    return {
        "tool": "aggregate_metrics",
        "launch_day": launch_day,
        "total_metrics": total,
        "breached_metrics": breached_count,
        "healthy_metrics": healthy_count,
        "health_score_pct": health_score,
        "metrics": results,
    }


if __name__ == "__main__":
    import json, pprint
    with open("../data/metrics.json") as f:
        data = json.load(f)
    result = aggregate_metrics(data)
    print(f"\n=== aggregate_metrics output ===")
    print(f"Health Score: {result['health_score_pct']}%")
    print(f"Breached: {result['breached_metrics']}/{result['total_metrics']} metrics")
    print("\nPer-metric summary:")
    for name, info in result["metrics"].items():
        status = "❌ BREACHED" if info["breached"] else "✅ OK"
        print(f"  {status} {name}: {info['latest_value']} {info['unit']} "
              f"(trend: {info['trend_last_3d']}, "
              f"Δ since launch: {info['pct_change_since_launch']}%)")