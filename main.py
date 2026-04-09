"""
main.py
Entry point for the War Room multi-agent system.

Usage:
    python main.py

Output:
    - warroom_output.json   — final structured decision
    - warroom_trace.log     — full agent + tool trace
"""

import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def load_inputs() -> tuple[dict, list, str]:
    base = os.path.dirname(os.path.abspath(__file__))

    with open(os.path.join(base, "data", "metrics.json")) as f:
        metrics = json.load(f)

    with open(os.path.join(base, "data", "feedback.json")) as f:
        feedback = json.load(f)

    with open(os.path.join(base, "data", "release_notes.md")) as f:
        release_notes = f.read()

    return metrics, feedback, release_notes


def main():
    print("\n" + "═" * 60)
    print("  🚨  PURPLEMERIT WAR ROOM  —  SMART PAYMENTS LAUNCH")
    print("═" * 60)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("\n[1/3] Loading dashboard inputs...")
    metrics, feedback, release_notes = load_inputs()
    print(f"      ✅ Metrics: {len(metrics['metrics'])} indicators over {len(list(metrics['metrics'].values())[0]['values'])} days")
    print(f"      ✅ Feedback: {len(feedback)} user entries")
    print(f"      ✅ Release notes loaded")

    # ── Build initial state ───────────────────────────────────────────────────
    initial_state = {
        "metrics":        metrics,
        "feedback":       feedback,
        "release_notes":  release_notes,
        "aggregation":    None,
        "anomalies":      None,
        "trends":         None,
        "sentiment":      None,
        "themes":         None,
        "analyst_report":   None,
        "sentiment_report": None,
        "pm_assessment":    None,
        "comms_plan":       None,
        "risk_flags":       [],
        "iteration_count":  0,
        "revision_history": [],
        "agent_status":     {},
        "final_decision":   None,
    }

    # ── Run graph ─────────────────────────────────────────────────────────────
    print("\n[2/3] Running war room agents...")
    print("      (see warroom_trace.log for full trace)\n")

    from graph import graph

    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        print(f"\n❌ Graph execution failed: {e}")
        raise

    # ── Save output ───────────────────────────────────────────────────────────
    print("\n[3/3] Saving structured output...")
    output = final_state.get("final_decision", {})

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "warroom_output.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  WAR ROOM DECISION")
    print("═" * 60)
    print(f"\n  DECISION        : {output.get('decision', 'N/A')}")
    print(f"  CONFIDENCE      : {output.get('confidence_score', 'N/A')}")
    print(f"  ITERATIONS      : {output.get('total_iterations', 'N/A')}")

    rationale = output.get("rationale", {})
    drivers = rationale.get("primary_drivers", [])
    if drivers:
        print(f"\n  PRIMARY DRIVERS :")
        for d in drivers:
            print(f"    • {d}")

    risks = output.get("risk_register", [])
    if risks:
        print(f"\n  TOP RISKS ({len(risks)})  :")
        for r in risks[:3]:
            print(f"    [{r.get('severity','?').upper()}] {r.get('risk','')}")

    actions = output.get("action_plan_24_48h", [])
    if actions:
        print(f"\n  ACTION PLAN     :")
        for a in actions[:4]:
            print(f"    [{a.get('priority','?')}] {a.get('action','')} — {a.get('owner','')} ({a.get('deadline','')})")

    print(f"\n  Output saved  → warroom_output.json")
    print(f"  Trace saved   → warroom_trace.log")
    print("\n" + "═" * 60 + "\n")


if __name__ == "__main__":
    main()
