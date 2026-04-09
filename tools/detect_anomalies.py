"""
Tool 2: detect_anomalies
Uses z-score analysis to flag statistically significant anomalies
in metric time series. Also flags sudden single-day spikes.
Called by: Data Analyst Agent
"""

from typing import Any


def _mean(values: list) -> float:
    return sum(values) / len(values)


def _std(values: list) -> float:
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return variance ** 0.5


def detect_anomalies(metrics_data: dict, z_threshold: float = 1.8) -> dict:
    """
    Detects anomalies in metric time series using z-score analysis.
    Also flags metrics with consecutive worsening days post-launch.

    Args:
        metrics_data: Full metrics.json dict
        z_threshold:  Z-score cutoff to flag a point as anomalous (default 1.8)

    Returns:
        Dict with anomalies per metric + severity classification
    """
    launch_day = metrics_data["launch_day"]
    anomalies  = {}
    critical_metrics = []
    warning_metrics  = []

    for metric_name, metric_info in metrics_data["metrics"].items():
        values   = metric_info["values"]
        days     = sorted(values.keys(), key=lambda d: int(d.split("_")[1]))
        series   = [values[d] for d in days]
        day_nums = [int(d.split("_")[1]) for d in days]

        threshold_max = metric_info.get("threshold_max")
        threshold_min = metric_info.get("threshold_min")

        # Z-score anomaly detection
        if len(series) < 3:
            continue

        mean_val = _mean(series)
        std_val  = _std(series)
        flagged_points = []

        for i, (day, val) in enumerate(zip(day_nums, series)):
            if std_val == 0:
                continue
            z = abs((val - mean_val) / std_val)
            if z >= z_threshold:
                direction = "spike" if val > mean_val else "drop"
                flagged_points.append({
                    "day":       day,
                    "value":     val,
                    "z_score":   round(z, 3),
                    "direction": direction,
                })

        # Consecutive worsening check (post-launch)
        post_launch = [
            (d, v) for d, v in zip(day_nums, series) if d >= launch_day
        ]
        consecutive_worsening = 0
        for i in range(1, len(post_launch)):
            prev_v = post_launch[i - 1][1]
            curr_v = post_launch[i][1]
            # Worsening = increasing for max-threshold metrics, decreasing for min
            if threshold_max and curr_v > prev_v:
                consecutive_worsening += 1
            elif threshold_min and curr_v < prev_v:
                consecutive_worsening += 1
            else:
                consecutive_worsening = 0  # reset on improvement

        # Rate of change acceleration (is it getting worse faster?)
        if len(post_launch) >= 3:
            recent_deltas = [
                post_launch[i][1] - post_launch[i-1][1]
                for i in range(1, len(post_launch))
            ]
            # Positive acceleration on a max-threshold metric = danger
            accelerating = False
            if threshold_max and len(recent_deltas) >= 2:
                accelerating = recent_deltas[-1] > recent_deltas[-2] > 0
            elif threshold_min and len(recent_deltas) >= 2:
                accelerating = recent_deltas[-1] < recent_deltas[-2] < 0
        else:
            accelerating = False
            recent_deltas = []

        # Severity classification
        breach_count = sum(
            1 for d, v in zip(day_nums, series)
            if (threshold_max and v > threshold_max) or
               (threshold_min and v < threshold_min)
        )

        if breach_count >= 3 or (breach_count >= 1 and accelerating):
            severity = "CRITICAL"
            critical_metrics.append(metric_name)
        elif breach_count >= 1 or consecutive_worsening >= 3:
            severity = "WARNING"
            warning_metrics.append(metric_name)
        elif len(flagged_points) > 0:
            severity = "WATCH"
        else:
            severity = "NORMAL"

        anomalies[metric_name] = {
            "severity":              severity,
            "breach_count":          breach_count,
            "z_score_anomalies":     flagged_points,
            "consecutive_worsening": consecutive_worsening,
            "accelerating":          accelerating,
            "post_launch_deltas":    [round(d, 3) for d in recent_deltas],
        }

    return {
        "tool":              "detect_anomalies",
        "z_threshold_used":  z_threshold,
        "critical_metrics":  critical_metrics,
        "warning_metrics":   warning_metrics,
        "anomaly_details":   anomalies,
        "overall_severity":  "CRITICAL" if critical_metrics else
                             "WARNING"  if warning_metrics  else "NORMAL",
    }


if __name__ == "__main__":
    import json
    with open("../data/metrics.json") as f:
        data = json.load(f)
    result = detect_anomalies(data)
    print(f"\n=== detect_anomalies output ===")
    print(f"Overall Severity: {result['overall_severity']}")
    print(f"Critical: {result['critical_metrics']}")
    print(f"Warning:  {result['warning_metrics']}")
    print("\nPer-metric anomaly details:")
    for name, info in result["anomaly_details"].items():
        if info["severity"] != "NORMAL":
            print(f"  [{info['severity']}] {name} — "
                  f"breaches: {info['breach_count']}, "
                  f"accelerating: {info['accelerating']}, "
                  f"consecutive_worsening: {info['consecutive_worsening']}")