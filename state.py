"""
state.py
Defines the shared WarRoomState TypedDict that flows through
every node in the LangGraph graph.
"""

from typing import TypedDict, Optional


class RiskFlag(TypedDict):
    severity: str          # "critical" | "warning" | "info"
    target: str            # "data" | "pm" | "comms" | "general"
    issue: str             # Human-readable description
    evidence: str          # What data backs this flag


class RevisionRecord(TypedDict):
    iteration:   int
    flagged_by:  str       # agent that raised the flag
    target:      str       # agent that needs to revise
    reason:      str       # why revision was requested
    resolved:    bool      # did the target agent address it


class WarRoomState(TypedDict):
    # ── Raw inputs ──────────────────────────────────────────
    metrics:        dict          # full metrics.json
    feedback:       list          # full feedback.json entries
    release_notes:  str           # release_notes.md content

    # ── Tool outputs (set by agents, read by downstream) ────
    aggregation:    Optional[dict]   # from aggregate_metrics()
    anomalies:      Optional[dict]   # from detect_anomalies()
    trends:         Optional[dict]   # from compare_trends()
    sentiment:      Optional[dict]   # from sentiment_summarizer()
    themes:         Optional[dict]   # from cluster_feedback_themes()

    # ── Agent reports ────────────────────────────────────────
    analyst_report:   Optional[str]   # Data Analyst Agent
    sentiment_report: Optional[str]   # Sentiment Agent
    pm_assessment:    Optional[str]   # PM Agent
    comms_plan:       Optional[str]   # Marketing/Comms Agent

    # ── Risk / loop control ──────────────────────────────────
    risk_flags:       list            # List[RiskFlag]
    iteration_count:  int             # how many Risk loops completed
    revision_history: list            # List[RevisionRecord] — full audit trail
    agent_status: dict                # {"analyst":"approved","pm":"needs_revision",...}

    # ── Final output ─────────────────────────────────────────
    final_decision:   Optional[dict]  # structured JSON decision