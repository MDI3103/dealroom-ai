"""
adk_config.py — Google ADK Agent Definitions
Registers all DealRoom AI agents as proper ADK Agent objects
with declared tools, capabilities, and safety settings.

In Google ADK, agents are defined with:
- A model (Gemini)
- A set of FunctionTools (MCP tools exposed as ADK tools)
- An instruction prompt
- Optional sub-agents (for hierarchical orchestration)
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

try:
    # Google ADK imports
    from google.adk.agents import Agent, LlmAgent
    from google.adk.tools import FunctionTool
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False


# Import all MCP tool functions
from mcp_tools.tools import (
    web_search,
    wikipedia_summary,
    crunchbase_lookup,
    get_financial_data,
    get_historical_prices,
    resolve_ticker,
    get_news,
    analyze_sentiment,
    get_reddit_mentions,
    search_legal_issues,
    search_founder_background,
)

GEMINI_MODEL = "gemini-1.5-flash"
API_KEY = os.getenv("GOOGLE_API_KEY", "")


def build_adk_agents():
    """
    Build and return all ADK agents with their registered MCP tools.
    Returns a dict of agent_id → ADK Agent object, or None if ADK is unavailable.
    """
    if not ADK_AVAILABLE:
        return None

    # ── Agent 1: Orchestrator ─────────────────────────────
    # (No tools — delegates to sub-agents via ADK multi-agent)
    orchestrator = LlmAgent(
        name="dealroom_orchestrator",
        model=GEMINI_MODEL,
        description="Orchestrates due diligence analysis by coordinating specialist sub-agents.",
        instruction="""
You are the DealRoom AI Orchestrator. When given a company name:
1. Validate the input for safety
2. Dispatch the four specialist agents in parallel
3. Collect their outputs
4. Synthesise into an investment-grade report
5. Flag any critical risks prominently

Always be factual and grounded. Do not fabricate financial data.
If data is unavailable, state it clearly rather than inventing numbers.
""",
    )

    # ── Agent 2: Market Research ──────────────────────────
    market_research = LlmAgent(
        name="market_research_agent",
        model=GEMINI_MODEL,
        description="Researches company overview, market size, competitors, and funding history.",
        instruction="""
You are a market research analyst. For the given company:
1. Fetch Wikipedia overview
2. Search for market size and TAM
3. Identify key competitors
4. Find funding history via Crunchbase

Be concise. Cite sources. If a tool fails, use the next available source.
""",
        tools=[
            FunctionTool(func=web_search),
            FunctionTool(func=wikipedia_summary),
            FunctionTool(func=crunchbase_lookup),
        ],
    )

    # ── Agent 3: Financial Analyst ────────────────────────
    financial_analyst = LlmAgent(
        name="financial_analyst_agent",
        model=GEMINI_MODEL,
        description="Fetches and analyses financial data: revenue, market cap, profitability, price history.",
        instruction="""
You are a financial analyst. For the given company:
1. Resolve the stock ticker (if public)
2. Fetch live financial data via yfinance
3. Get 1-year price history
4. Search for funding rounds if private

Present numbers clearly. Format large numbers as $XB or $XM.
Note if the company is private and data is estimated.
""",
        tools=[
            FunctionTool(func=resolve_ticker),
            FunctionTool(func=get_financial_data),
            FunctionTool(func=get_historical_prices),
            FunctionTool(func=web_search),
        ],
    )

    # ── Agent 4: Risk Assessor ────────────────────────────
    risk_assessor = LlmAgent(
        name="risk_assessor_agent",
        model=GEMINI_MODEL,
        description="Identifies legal, regulatory, and operational risks. Sends A2A flags on critical findings.",
        instruction="""
You are a risk analyst. For the given company:
1. Search for lawsuits, fines, and regulatory actions
2. Check founder and executive background
3. Assess regulatory environment
4. Classify all findings by severity: critical / high / medium / low

If you find critical or high-severity issues, note them prominently.
These will trigger re-analysis by the financial analyst via A2A.
""",
        tools=[
            FunctionTool(func=search_legal_issues),
            FunctionTool(func=search_founder_background),
            FunctionTool(func=web_search),
        ],
    )

    # ── Agent 5: Sentiment & News ─────────────────────────
    sentiment_agent = LlmAgent(
        name="sentiment_news_agent",
        model=GEMINI_MODEL,
        description="Analyses recent news coverage and public sentiment.",
        instruction="""
You are a media and sentiment analyst. For the given company:
1. Fetch recent news articles (NewsAPI → Google RSS fallback)
2. Analyse sentiment per article
3. Check Reddit community discussions
4. Run a targeted reputation search

Provide a clear overall sentiment: Positive / Neutral / Negative.
List the top 5 most significant headlines.
""",
        tools=[
            FunctionTool(func=get_news),
            FunctionTool(func=analyze_sentiment),
            FunctionTool(func=get_reddit_mentions),
            FunctionTool(func=web_search),
        ],
    )

    return {
        "orchestrator": orchestrator,
        "market_research": market_research,
        "financial_analyst": financial_analyst,
        "risk_assessor": risk_assessor,
        "sentiment_news": sentiment_agent,
    }


def get_adk_runner(agent_name: str = "dealroom_orchestrator"):
    """
    Build an ADK Runner for local or cloud execution.
    Used for running agents via the ADK runtime (adk run / adk web).
    """
    if not ADK_AVAILABLE:
        raise ImportError(
            "google-adk is not installed. Run: pip install google-adk"
        )

    agents = build_adk_agents()
    session_service = InMemorySessionService()

    runner = Runner(
        agent=agents[agent_name.replace("dealroom_", "").replace("_agent", "")],
        app_name="dealroom_ai",
        session_service=session_service,
    )
    return runner


# ── ADK Agent Card (JSON) ─────────────────────────────────
# This is the A2A-compatible agent card that other agents can discover
AGENT_CARD = {
    "name": "DealRoom AI",
    "version": "1.0.0",
    "description": "Multi-agent M&A and startup due diligence system",
    "url": "http://localhost:8000",
    "capabilities": {
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": True,
    },
    "skills": [
        {
            "id": "company_due_diligence",
            "name": "Company Due Diligence",
            "description": "Full investment-grade due diligence report for any company",
            "tags": ["finance", "research", "M&A", "investment"],
            "examples": ["Analyse Grab", "Due diligence on Notion", "Research Tesla"],
            "inputModes": ["text"],
            "outputModes": ["text", "data"],
        }
    ],
    "agents": [
        {"id": "market_research_agent", "role": "Market research, competitors, funding"},
        {"id": "financial_analyst_agent", "role": "Financial data, valuations, price history"},
        {"id": "risk_assessor_agent", "role": "Legal risks, regulatory exposure, red flags"},
        {"id": "sentiment_news_agent", "role": "News sentiment, PR reputation, Reddit"},
    ],
    "authentication": {"schemes": ["none"]},
}
