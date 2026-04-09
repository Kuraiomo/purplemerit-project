"""
graph.py
Defines the full LangGraph state machine for the War Room system.

Graph flow:
  START
    → data_analyst          (runs 3 tools, writes analyst_report)
    → sentiment_agent       (runs 2 tools, writes sentiment_report)
    → pm_agent              (reads analyst + sentiment, writes pm_assessment)
    → marketing_agent       (reads sentiment + pm, writes comms_plan)
    → risk_critic_agent     (reads ALL, writes risk_flags)
    → [conditional router]
          ├── "data_analyst"      if data anomaly unresolved
          ├── "pm_agent"          if PM framing challenged
          ├── "marketing_agent"   if comms plan challenged
          └── "executive_summary" if all clear OR max iterations hit
    → executive_summary_agent  (synthesises everything → final_decision)
    → END
"""

import os
import json
import logging
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

from state import WarRoomState
from tools.aggregate_metrics import aggregate_metrics
from tools.detect_anomalies import detect_anomalies
from tools.compare_trends import compare_trends
from tools.sentiment_summarizer import sentiment_summarizer
from tools.cluster_feedback_themes import cluster_feedback_themes

load_dotenv()

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("warroom_trace.log", mode="w"),
    ],
)
log = logging.getLogger("warroom")

MAX_ITERATIONS = 2  # Risk Agent can loop at most this many times

# ── LLM initialisation ───────────────────────────────────────────────────────
def get_llm(temperature: float = 0.2) -> ChatGroq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not set in environment variables.")
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=temperature,
        groq_api_key=api_key,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 1 — Data Analyst Agent
# ═══════════════════════════════════════════════════════════════════════════════
def data_analyst_node(state: WarRoomState) -> dict:
    log.info("NODE: data_analyst_node | iteration=%d", state["iteration_count"])

    # ── Tool calls (deterministic Python) ────────────────────────────────────
    log.info("TOOL CALL: aggregate_metrics()")
    agg = aggregate_metrics(state["metrics"])

    log.info("TOOL CALL: detect_anomalies()")
    anoms = detect_anomalies(state["metrics"])

    log.info("TOOL CALL: compare_trends()")
    trends = compare_trends(state["metrics"])

    # ── Build context for LLM ────────────────────────────────────────────────
    revision_context = ""
    if state["iteration_count"] > 0:
        prev_flags = [
            f for f in state["risk_flags"]
            if f["target"] == "data"
        ]
        if prev_flags:
            revision_context = (
                "\n\nNOTE — You are re-analysing because the Risk Agent flagged:\n"
                + "\n".join(f"- {f['issue']}" for f in prev_flags)
                + "\nPlease address these concerns explicitly in your revised report."
            )

    prompt = f"""You are the Data Analyst in a product launch war room.
You have just run three analytical tools on the launch metrics.

=== TOOL OUTPUT: aggregate_metrics ===
Health Score: {agg['health_score_pct']}%
Breached metrics ({agg['breached_metrics']}/{agg['total_metrics']}):
{json.dumps({k: {
    'latest_value': v['latest_value'],
    'unit': v['unit'],
    'breached': v['breached'],
    'first_breach_day': v['first_breach_day'],
    'trend_last_3d': v['trend_last_3d'],
    'pct_change_since_launch': v['pct_change_since_launch']
} for k, v in agg['metrics'].items()}, indent=2)}

=== TOOL OUTPUT: detect_anomalies ===
Overall Severity: {anoms['overall_severity']}
Critical metrics: {anoms['critical_metrics']}
Warning metrics: {anoms['warning_metrics']}
Details:
{json.dumps({k: {
    'severity': v['severity'],
    'breach_count': v['breach_count'],
    'accelerating': v['accelerating'],
    'consecutive_worsening': v['consecutive_worsening']
} for k, v in anoms['anomaly_details'].items()}, indent=2)}

=== TOOL OUTPUT: compare_trends ===
Launch Impact: {trends['launch_impact']} (score: {trends['impact_score']})
Degraded: {trends['degraded']}
Improved: {trends['improved']}
{revision_context}

Write a concise analyst report (max 300 words) covering:
1. The 3 most critical metric findings with specific numbers
2. Which metrics look deceptively healthy vs are actually degrading
3. Your overall data-driven severity verdict (CRITICAL / WARNING / STABLE)
4. One key open question the data cannot yet answer

Be direct. Reference specific metric names and values."""

    llm = get_llm()
    log.info("LLM CALL: data_analyst reasoning")
    response = llm.invoke(prompt)
    report = response.content

    log.info("data_analyst_node complete | health_score=%s%% | severity=%s",
             agg['health_score_pct'], anoms['overall_severity'])

    return {
        "aggregation":    agg,
        "anomalies":      anoms,
        "trends":         trends,
        "analyst_report": report,
        "agent_status":   {**state.get("agent_status", {}), "analyst": "completed"},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 2 — Sentiment Agent
# ═══════════════════════════════════════════════════════════════════════════════
def sentiment_agent_node(state: WarRoomState) -> dict:
    log.info("NODE: sentiment_agent_node")

    # ── Tool calls ────────────────────────────────────────────────────────────
    log.info("TOOL CALL: sentiment_summarizer()")
    sent = sentiment_summarizer(state["feedback"])

    log.info("TOOL CALL: cluster_feedback_themes()")
    themes = cluster_feedback_themes(state["feedback"])

    prompt = f"""You are the Sentiment Analyst in a product launch war room.
You have analysed user feedback using two tools.

=== TOOL OUTPUT: sentiment_summarizer ===
Verdict: {sent['verdict']}
Distribution: {sent['distribution']}
Avg compound score: {sent['avg_compound_score']} (range: -1.0 to +1.0)
Daily sentiment trend: {json.dumps(sent['daily_sentiment'], indent=2)}
Top negative quotes:
{json.dumps(sent['top_negative_quotes'], indent=2)}

=== TOOL OUTPUT: cluster_feedback_themes ===
Dominant issue: {themes['dominant_issue']}
Escalating themes (3+ consecutive days): {themes['escalating_themes']}
Ranked issues: {json.dumps(themes['ranked_issues'], indent=2)}
Theme details (first seen, days active):
{json.dumps({k: {
    'count': v['count'],
    'avg_rating': v['avg_rating'],
    'first_seen_day': v['first_seen_day'],
    'days_active': v['days_active'],
    'representative_quote': v['representative_quote']
} for k, v in themes['theme_details'].items()}, indent=2)}

Write a concise sentiment report (max 250 words) covering:
1. Overall sentiment verdict and what drove it
2. The top 2-3 user complaints with frequency and severity
3. Whether sentiment is improving or worsening day-over-day
4. Any feedback that suggests financial or legal risk to the company
5. What users are saying that the metrics alone don't capture

Be direct and specific. Quote actual user feedback where impactful."""

    llm = get_llm()
    log.info("LLM CALL: sentiment_agent reasoning")
    response = llm.invoke(prompt)
    report = response.content

    log.info("sentiment_agent_node complete | verdict=%s | dominant_issue=%s",
             sent['verdict'], themes['dominant_issue'])

    return {
        "sentiment":        sent,
        "themes":           themes,
        "sentiment_report": report,
        "agent_status":     {**state.get("agent_status", {}), "sentiment": "completed"},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 3 — PM Agent
# ═══════════════════════════════════════════════════════════════════════════════
def pm_agent_node(state: WarRoomState) -> dict:
    log.info("NODE: pm_agent_node | iteration=%d", state["iteration_count"])

    revision_context = ""
    if state["iteration_count"] > 0:
        prev_flags = [f for f in state["risk_flags"] if f["target"] == "pm"]
        if prev_flags:
            revision_context = (
                "\n\nNOTE — You are revising your assessment because the Risk Agent challenged:\n"
                + "\n".join(f"- {f['issue']}" for f in prev_flags)
                + "\nYou must address each challenge explicitly."
            )

    prompt = f"""You are the Product Manager in a product launch war room for the Smart Payments feature.

=== SUCCESS CRITERIA (defined pre-launch) ===
- Payment success rate ≥ 95%
- Crash rate ≤ 1.5%
- API p95 latency ≤ 800ms
- D1 Retention ≥ 35%
- Support tickets ≤ 150/day
- Funnel completion ≥ 60%

=== DATA ANALYST REPORT ===
{state['analyst_report']}

=== SENTIMENT REPORT ===
{state['sentiment_report']}

=== RELEASE NOTES / KNOWN ISSUES ===
{state['release_notes']}
{revision_context}

Write a PM assessment (max 300 words) covering:
1. How many success criteria are currently met vs breached
2. User impact assessment — who is affected and how severely
3. Your initial go/no-go framing: Proceed / Pause / Roll Back with reasoning
4. What conditions would need to change to alter your recommendation
5. Business risk if we proceed vs if we pause

Be honest. Don't spin the numbers. Reference specific metrics."""

    llm = get_llm()
    log.info("LLM CALL: pm_agent reasoning")
    response = llm.invoke(prompt)
    assessment = response.content

    log.info("pm_agent_node complete")

    return {
        "pm_assessment": assessment,
        "agent_status":  {**state.get("agent_status", {}), "pm": "completed"},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 4 — Marketing / Comms Agent
# ═══════════════════════════════════════════════════════════════════════════════
def marketing_agent_node(state: WarRoomState) -> dict:
    log.info("NODE: marketing_agent_node | iteration=%d", state["iteration_count"])

    revision_context = ""
    if state["iteration_count"] > 0:
        prev_flags = [f for f in state["risk_flags"] if f["target"] == "comms"]
        if prev_flags:
            revision_context = (
                "\n\nNOTE — Revise your comms plan. The Risk Agent flagged:\n"
                + "\n".join(f"- {f['issue']}" for f in prev_flags)
            )

    prompt = f"""You are the Marketing/Comms lead in a product launch war room.

=== SENTIMENT REPORT ===
{state['sentiment_report']}

=== PM ASSESSMENT ===
{state['pm_assessment']}

=== TOP USER COMPLAINTS ===
Dominant issue: {state['themes']['dominant_issue']}
Escalating themes: {state['themes']['escalating_themes']}
Ranked issues: {json.dumps(state['themes']['ranked_issues'], indent=2)}
{revision_context}

Write a comms plan (max 300 words) covering:
1. Current customer perception risk (1-10 scale with reasoning)
2. Draft internal Slack message to the team (2-3 sentences)
3. Draft external status page message for affected users (2-3 sentences)
4. Whether a proactive customer email is needed and why
5. Key messaging DO's and DON'Ts given the duplicate charge and crash reports

Be precise. Assume some users have already posted on social media."""

    llm = get_llm()
    log.info("LLM CALL: marketing_agent reasoning")
    response = llm.invoke(prompt)
    plan = response.content

    log.info("marketing_agent_node complete")

    return {
        "comms_plan":   plan,
        "agent_status": {**state.get("agent_status", {}), "marketing": "completed"},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 5 — Risk / Critic Agent
# ═══════════════════════════════════════════════════════════════════════════════
def risk_critic_node(state: WarRoomState) -> dict:
    log.info("NODE: risk_critic_node | iteration=%d", state["iteration_count"])

    prompt = f"""You are the Risk/Critic Agent in a product launch war room. Your job is to 
challenge assumptions, surface blind spots, and decide whether any agent needs to revise 
their output before a final decision is made.

This is review iteration {state['iteration_count'] + 1} of maximum {MAX_ITERATIONS}.

=== ANALYST REPORT ===
{state['analyst_report']}

=== SENTIMENT REPORT ===
{state['sentiment_report']}

=== PM ASSESSMENT ===
{state['pm_assessment']}

=== COMMS PLAN ===
{state['comms_plan']}

=== KEY METRICS SNAPSHOT ===
- Payment success rate (day 10): {state['aggregation']['metrics']['payment_success_rate_pct']['latest_value']}% (threshold: 95%)
- Crash rate (day 10): {state['aggregation']['metrics']['crash_rate_pct']['latest_value']}% (threshold: 1.5%)
- API latency p95 (day 10): {state['aggregation']['metrics']['api_latency_p95_ms']['latest_value']}ms (threshold: 800ms)
- Support tickets (day 10): {state['aggregation']['metrics']['support_ticket_volume']['latest_value']} (threshold: 150)
- Duplicate charge reports: YES (user feedback)
- Crash rate trend: ACCELERATING post-launch

=== PREVIOUS REVISION HISTORY ===
{json.dumps(state['revision_history'], indent=2) if state['revision_history'] else "None — first review."}

Your task:
1. Identify the 2-3 most dangerous assumptions or gaps in the above reports
2. For each gap, decide: does it need an agent revision, or just a flag?
3. Produce a structured JSON block at the END of your response in this exact format:

<RISK_FLAGS>
{{
  "flags": [
    {{
      "severity": "critical|warning|info",
      "target": "data|pm|comms|general",
      "issue": "one sentence description",
      "evidence": "specific metric or quote that supports this"
    }}
  ],
  "request_revision": {{
    "data": true|false,
    "pm": true|false,
    "comms": true|false
  }},
  "critic_verdict": "APPROVE|REVISE",
  "critic_summary": "2-3 sentence overall critique"
}}
</RISK_FLAGS>

Be a tough critic. Do not approve if there are unaddressed critical risks.
If iteration is {MAX_ITERATIONS}, you MUST set critic_verdict to APPROVE regardless."""

    llm = get_llm(temperature=0.1)
    log.info("LLM CALL: risk_critic reasoning")
    response = llm.invoke(prompt)
    raw = response.content

    # ── Parse the structured JSON block ──────────────────────────────────────
    risk_data = {
        "flags": [],
        "request_revision": {"data": False, "pm": False, "comms": False},
        "critic_verdict": "APPROVE",
        "critic_summary": raw,
    }

    try:
        start = raw.find("<RISK_FLAGS>") + len("<RISK_FLAGS>")
        end   = raw.find("</RISK_FLAGS>")
        if start > len("<RISK_FLAGS>") - 1 and end != -1:
            json_str  = raw[start:end].strip()
            risk_data = json.loads(json_str)
            log.info("risk_critic parsed flags: %d flags | verdict: %s",
                     len(risk_data.get("flags", [])),
                     risk_data.get("critic_verdict"))
    except Exception as e:
        log.warning("risk_critic JSON parse failed: %s — defaulting to APPROVE", e)
        risk_data["critic_verdict"] = "APPROVE"

    # Force APPROVE if max iterations reached
    if state["iteration_count"] >= MAX_ITERATIONS:
        log.info("MAX_ITERATIONS reached — forcing APPROVE")
        risk_data["critic_verdict"] = "APPROVE"
        risk_data["critic_summary"] += (
            "\n[NOTE: Max iterations reached. Proceeding with unresolved flags. "
            "Confidence score will be penalised in final output.]"
        )

    # Build revision record for audit trail
    revision_record = {
        "iteration":  state["iteration_count"] + 1,
        "flagged_by": "risk_critic",
        "target":     str(risk_data.get("request_revision", {})),
        "reason":     risk_data.get("critic_summary", "")[:200],
        "resolved":   risk_data.get("critic_verdict") == "APPROVE",
    }

    new_flags    = state.get("risk_flags", []) + risk_data.get("flags", [])
    new_history  = state.get("revision_history", []) + [revision_record]

    log.info("risk_critic_node complete | verdict=%s | iteration=%d",
             risk_data["critic_verdict"], state["iteration_count"])

    return {
        "risk_flags":       new_flags,
        "revision_history": new_history,
        "iteration_count":  state["iteration_count"] + 1,
        "agent_status":     {**state.get("agent_status", {}), "risk": "completed"},
        "_risk_data":       risk_data,   # temp key for router
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 6 — Executive Summary Agent
# ═══════════════════════════════════════════════════════════════════════════════
def executive_summary_node(state: WarRoomState) -> dict:
    log.info("NODE: executive_summary_node")

    # Confidence penalty for unresolved risk loops
    base_confidence = 0.85
    penalty = 0.08 * max(0, state["iteration_count"] - 1)
    unresolved_critical = sum(
        1 for f in state["risk_flags"] if f["severity"] == "critical"
    )
    penalty += 0.05 * unresolved_critical
    confidence = round(max(0.30, base_confidence - penalty), 2)

    prompt = f"""You are the Executive Summary Agent. Your job is to synthesise all 
war room agent outputs into a single structured final decision.

=== ALL AGENT REPORTS ===

ANALYST REPORT:
{state['analyst_report']}

SENTIMENT REPORT:
{state['sentiment_report']}

PM ASSESSMENT:
{state['pm_assessment']}

COMMS PLAN:
{state['comms_plan']}

RISK FLAGS ({len(state['risk_flags'])} total):
{json.dumps(state['risk_flags'], indent=2)}

REVISION HISTORY:
{json.dumps(state['revision_history'], indent=2)}

=== KEY METRICS (day 10 snapshot) ===
- Payment success rate: {state['aggregation']['metrics']['payment_success_rate_pct']['latest_value']}% (threshold 95%) ❌
- Crash rate: {state['aggregation']['metrics']['crash_rate_pct']['latest_value']}% (threshold 1.5%) ❌
- API latency p95: {state['aggregation']['metrics']['api_latency_p95_ms']['latest_value']}ms (threshold 800ms) ❌
- Support tickets/day: {state['aggregation']['metrics']['support_ticket_volume']['latest_value']} (threshold 150) ❌
- D1 Retention: {state['aggregation']['metrics']['d1_retention_pct']['latest_value']}% (threshold 35%) ❌
- DAU: {state['aggregation']['metrics']['dau']['latest_value']} (threshold 8000) ✅
- Activation conversion: {state['aggregation']['metrics']['activation_conversion_pct']['latest_value']}% (threshold 40%) ✅

Confidence score for this decision: {confidence} (penalised for {state['iteration_count']-1} unresolved loop(s) and {unresolved_critical} critical flags)

Produce ONLY a valid JSON object (no markdown, no preamble) with this exact structure:
{{
  "decision": "Proceed|Pause|Roll Back",
  "confidence_score": {confidence},
  "rationale": {{
    "primary_drivers": ["list of 3-4 key factors that determined the decision"],
    "metrics_summary": "2-3 sentence summary referencing specific metric values",
    "feedback_summary": "2-3 sentence summary of user feedback themes"
  }},
  "risk_register": [
    {{
      "risk": "risk description",
      "severity": "critical|high|medium",
      "mitigation": "specific mitigation action"
    }}
  ],
  "action_plan_24_48h": [
    {{
      "action": "specific action",
      "owner": "team/role responsible",
      "deadline": "24h|48h",
      "priority": "P0|P1|P2"
    }}
  ],
  "communication_plan": {{
    "internal": "draft internal message",
    "external": "draft status page message",
    "proactive_email_needed": true|false,
    "proactive_email_rationale": "why or why not"
  }},
  "what_would_increase_confidence": ["list of 3-4 specific conditions"],
  "agents_consulted": ["data_analyst","sentiment_agent","pm_agent","marketing_agent","risk_critic"],
  "total_iterations": {state['iteration_count']}
}}"""

    llm = get_llm(temperature=0.1)
    log.info("LLM CALL: executive_summary synthesis")
    response = llm.invoke(prompt)
    raw = response.content

    # ── Parse JSON ────────────────────────────────────────────────────────────
    final_decision = {}
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        final_decision = json.loads(clean.strip())
        log.info("executive_summary parsed | decision=%s | confidence=%s",
                 final_decision.get("decision"), final_decision.get("confidence_score"))
    except Exception as e:
        log.error("executive_summary JSON parse failed: %s", e)
        final_decision = {"decision": "Pause", "raw_output": raw,
                          "parse_error": str(e), "confidence_score": confidence}

    return {
        "final_decision": final_decision,
        "agent_status":   {**state.get("agent_status", {}), "executive": "completed"},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CONDITIONAL ROUTER — after Risk Critic
# ═══════════════════════════════════════════════════════════════════════════════
def risk_router(state: WarRoomState) -> str:
    """
    Inspects the risk_critic output and decides which node to route to next.
    Returns the node name as a string.
    """
    risk_data    = state.get("_risk_data", {})
    verdict      = risk_data.get("critic_verdict", "APPROVE")
    revisions    = risk_data.get("request_revision", {})
    iterations   = state["iteration_count"]

    log.info("ROUTER: verdict=%s | revisions=%s | iteration=%d",
             verdict, revisions, iterations)

    if verdict == "APPROVE" or iterations >= MAX_ITERATIONS:
        log.info("ROUTER → executive_summary")
        return "executive_summary"

    # Priority order: data issues > pm issues > comms issues
    if revisions.get("data"):
        log.info("ROUTER → data_analyst (revision requested)")
        return "data_analyst"

    if revisions.get("pm"):
        log.info("ROUTER → pm_agent (revision requested)")
        return "pm_agent"

    if revisions.get("comms"):
        log.info("ROUTER → marketing_agent (revision requested)")
        return "marketing_agent"

    log.info("ROUTER → executive_summary (no revisions needed)")
    return "executive_summary"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════
def build_graph():
    builder = StateGraph(WarRoomState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("data_analyst",       data_analyst_node)
    builder.add_node("sentiment_agent",    sentiment_agent_node)
    builder.add_node("pm_agent",           pm_agent_node)
    builder.add_node("marketing_agent",    marketing_agent_node)
    builder.add_node("risk_critic",        risk_critic_node)
    builder.add_node("executive_summary",  executive_summary_node)

    # ── Linear edges ─────────────────────────────────────────────────────────
    builder.add_edge(START,             "data_analyst")
    builder.add_edge("data_analyst",    "sentiment_agent")
    builder.add_edge("sentiment_agent", "pm_agent")
    builder.add_edge("pm_agent",        "marketing_agent")
    builder.add_edge("marketing_agent", "risk_critic")
    builder.add_edge("executive_summary", END)

    # ── Conditional edge (the feedback loop) ─────────────────────────────────
    builder.add_conditional_edges(
        "risk_critic",
        risk_router,
        {
            "data_analyst":      "data_analyst",
            "pm_agent":          "pm_agent",
            "marketing_agent":   "marketing_agent",
            "executive_summary": "executive_summary",
        }
    )

    return builder.compile()


# ── Export ────────────────────────────────────────────────────────────────────
graph = build_graph()