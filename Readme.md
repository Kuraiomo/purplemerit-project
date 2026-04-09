# War Room — Multi-Agent Product Launch Decision System

A multi-agent system that simulates a cross-functional war room during a product launch. Agents analyse a mock dashboard (metrics + user feedback) and produce a structured launch decision: **Proceed / Pause / Roll Back**, along with a full action plan.

Built for the **Purple Merit Technologies — AI/ML Engineer Assessment**.

---

## Architecture

```
[START]
   │
   ▼
[Data Analyst Agent]       ← runs: aggregate_metrics(), detect_anomalies(), compare_trends()
   │
   ▼
[Sentiment Agent]          ← runs: sentiment_summarizer(), cluster_feedback_themes()
   │
   ▼
[PM Agent]                 ← reads: analyst_report + sentiment_report
   │
   ▼
[Marketing/Comms Agent]    ← reads: sentiment_report + pm_assessment
   │
   ▼
[Risk/Critic Agent]        ← reads: ALL reports → emits structured risk_flags + verdict
   │
   ├── "data needs re-examination"  ──► [Data Analyst Agent]  ─┐
   ├── "PM framing challenged"      ──► [PM Agent]             │ (max 2 loops)
   ├── "comms plan challenged"      ──► [Marketing Agent]      │
   │                                                            │
   └── "all clear" OR max iterations ──────────────────────────┘
                                          │
                                          ▼
                              [Executive Summary Agent]  ← synthesises all outputs
                                          │
                                         [END] → warroom_output.json
```

### Agents (6 total)

| Agent | Responsibility | Tools Used |
|---|---|---|
| Data Analyst | Quantitative metric analysis, anomaly detection, trend comparison | `aggregate_metrics`, `detect_anomalies`, `compare_trends` |
| Sentiment Agent | User feedback scoring, theme clustering | `sentiment_summarizer`, `cluster_feedback_themes` |
| PM Agent | Success criteria evaluation, go/no-go framing | — |
| Marketing/Comms Agent | Customer perception, internal/external messaging | — |
| Risk/Critic Agent | Challenges assumptions, triggers revision loops | — |
| Executive Summary Agent | Final decision synthesis → structured JSON | — |

### Tools (5 total — deterministic Python, no LLM)

| Tool | What it does |
|---|---|
| `aggregate_metrics` | Rolling averages, day-over-day deltas, threshold breach detection |
| `detect_anomalies` | Z-score analysis, consecutive worsening, acceleration detection |
| `compare_trends` | Baseline vs launch window comparison, launch impact scoring |
| `sentiment_summarizer` | VADER sentiment scoring, daily trend, top quotes |
| `cluster_feedback_themes` | Keyword-based theme clustering, escalation detection |

### Feedback Loop

The Risk/Critic Agent can route back to earlier agents (up to **2 iterations**) if it finds unresolved critical issues. Each loop is recorded in `revision_history`. If max iterations are reached, the system proceeds with a penalised confidence score and a note in the output.

---

## Project Structure

```
warroom/
├── main.py                    # Entry point
├── graph.py                   # LangGraph state machine (all 6 nodes + router)
├── state.py                   # WarRoomState TypedDict
├── requirements.txt
├── .env.example               # Copy to .env and fill in GROQ_API_KEY
├── .gitignore
├── data/
│   ├── metrics.json           # 10-day time series (11 metrics)
│   ├── feedback.json          # 30 user feedback entries
│   └── release_notes.md       # Feature description + known risks
└── tools/
    ├── __init__.py
    ├── aggregate_metrics.py
    ├── detect_anomalies.py
    ├── compare_trends.py
    ├── sentiment_summarizer.py
    └── cluster_feedback_themes.py
```

---

## Setup

### Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com) (no credit card required)

### 1. Clone the repository

```bash
git clone https://github.com/Kuraiomo/warroom-agent.git
cd warroom-agent
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your Groq API key

```bash
cp .env.example .env
```

Open `.env` and set your key:

```
GROQ_API_KEY=your_groq_api_key_here
```

> **Never commit `.env` to version control.** It is already in `.gitignore`.

---

## Running the System

```bash
python main.py
```

The system will:
1. Load the mock dashboard (metrics + feedback + release notes)
2. Run all 6 agents through the LangGraph state machine
3. Print a decision summary to the console
4. Save the full structured output to `warroom_output.json`
5. Save the full agent + tool trace to `warroom_trace.log`

**Expected runtime:** ~30–60 seconds depending on Groq response times.

---

## Output Files

### `warroom_output.json`

The final structured decision in JSON format:

```json
{
  "decision": "Pause",
  "confidence_score": 0.72,
  "rationale": {
    "primary_drivers": [...],
    "metrics_summary": "...",
    "feedback_summary": "..."
  },
  "risk_register": [
    {
      "risk": "...",
      "severity": "critical",
      "mitigation": "..."
    }
  ],
  "action_plan_24_48h": [
    {
      "action": "...",
      "owner": "...",
      "deadline": "24h",
      "priority": "P0"
    }
  ],
  "communication_plan": {
    "internal": "...",
    "external": "...",
    "proactive_email_needed": true,
    "proactive_email_rationale": "..."
  },
  "what_would_increase_confidence": [...],
  "agents_consulted": [...],
  "total_iterations": 1
}
```

### `warroom_trace.log`

Full execution trace showing every agent entry, tool call, LLM call, and routing decision. Format:

```
2026-04-09 10:00:01 | INFO | warroom | NODE: data_analyst_node | iteration=0
2026-04-09 10:00:01 | INFO | warroom | TOOL CALL: aggregate_metrics()
2026-04-09 10:00:01 | INFO | warroom | TOOL CALL: detect_anomalies()
2026-04-09 10:00:01 | INFO | warroom | TOOL CALL: compare_trends()
2026-04-09 10:00:02 | INFO | warroom | LLM CALL: data_analyst reasoning
...
2026-04-09 10:00:45 | INFO | warroom | ROUTER: verdict=REVISE | revisions={'data': False, 'pm': True, 'comms': False} | iteration=1
2026-04-09 10:00:45 | INFO | warroom | ROUTER → pm_agent (revision requested)
...
2026-04-09 10:01:10 | INFO | warroom | executive_summary parsed | decision=Pause | confidence=0.72
```

Traces are located at `warroom_trace.log` in the project root. Each line follows the pattern:
`timestamp | level | logger | message`

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | Your Groq API key from [console.groq.com](https://console.groq.com) |

---

## Scenario

**Feature:** Smart Payments v1.0 — a redesigned one-tap payment flow for PurpleMerit.

**Launch window:** 10 days of monitoring data. The feature shows healthy DAU and activation numbers on the surface, but underlying metrics (crash rate, payment success rate, API latency, support tickets) degrade sharply post-launch. User feedback reveals duplicate charges and app crashes during payment submission.

**Expected decision:** `Pause` — conditions are too unstable to proceed, but not severe enough to require a full rollback given the feature flag toggle available.

---

## Model Used

**Groq:** `llama-3.3-70b-versatile` — fast, free tier available, strong reasoning for structured output tasks.
