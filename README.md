# 🏦 DealRoom AI

> Investment-grade due diligence in under 60 seconds — powered by 5 parallel AI agents

Built for the **Google ADK + A2A + MCP Hackathon**

---

## What It Does

Type any company name. DealRoom AI dispatches 5 specialist agents in parallel
that collaborate via the A2A protocol to produce an institutional-grade
investment report in under 30 seconds.



## Tech Stack

| Layer | Technology |
|---|---|
| Agent Framework | Google ADK |
| Agent Communication | A2A Protocol |
| Tool Layer | MCP (Model Context Protocol) |
| LLM | Gemini 2.0 Flash |
| Market Data | yFinance |
| News & Sentiment | NewsAPI + Google News RSS |
| Web Intelligence | Tavily Search |
| Frontend | Streamlit + Plotly |

---

## Features

- 5 parallel agents dispatched simultaneously via Google ADK
- A2A messaging — Risk Agent flags Financial Agent in real time
- Guardrails — injection detection, PII scrubbing, rate limiting
- Live trace panel — watch every agent step as it happens
- Bloomberg-grade dashboard — price history, financials, competitors
- Goldman Sachs-style report — thesis, bull/bear case, price target
- 1-hour result cache with force-refresh toggle
- Kill agent demo — simulate failure and watch recovery live

---

## Quick Start

### Prerequisites
- Python 3.11+
- API keys (see below)

### Installation

\\\ash
git clone https://github.com/YOUR_USERNAME/dealroom-ai
cd dealroom-ai
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
\\\

### API Keys

Create a \.env\ file in the project root:

\\\
GOOGLE_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
\\\

| Key | Get it from | Free tier |
|---|---|---|
| GOOGLE_API_KEY | aistudio.google.com | Yes |
| TAVILY_API_KEY | tavily.com | 1000/month |
| NEWS_API_KEY | newsapi.org | 100/day |

### Run

\\\ash
streamlit run frontend/app.py
\\\

Open http://localhost:8501 — type any company and hit Analyse.

---

## Project Structure

\\\
dealroom-ai/
├── agents/
│   ├── market_research_agent.py
│   ├── financial_analyst_agent.py
│   ├── risk_assessor_agent.py
│   ├── sentiment_news_agent.py
│   └── competitor_agent.py
├── orchestrator/
│   └── orchestrator_agent.py
├── a2a/
│   └── messaging.py
├── mcp_tools/
│   └── tools.py
├── guardrails/
│   └── safety.py
├── frontend/
│   └── app.py
├── utils/
│   ├── cache.py
│   └── report_formatter.py
└── main.py
\\\

---

## Hackathon Criteria

| Criteria | Implementation |
|---|---|
| Agentic Agency and Recovery 40% | Kill-agent demo, automatic fallback, A2A cross-agent flags |
| Technical Depth ADK/MCP 30% | Full ADK orchestration, 8 MCP tools, A2A protocol |
| System Robustness 20% | Guardrails, rate limiting, PII scrubbing, input validation |
| Docs and Demo 10% | README, live dashboard, screen recording |

---

## Author

Built for the Google ADK Hackathon 2025
