"""
Agent 2 — Market Research Agent
Tools: web_search (Tavily), wikipedia, crunchbase_lookup
Produces: company overview, competitors, market size, funding history
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from agents.base_agent import BaseAgent
from mcp_tools.tools import web_search, wikipedia_summary, crunchbase_lookup


class MarketResearchAgent(BaseAgent):
    """
    Researches company overview, market positioning, and competitors.

    MCP Toolbox:
    - web_search     → Tavily API (fallback: DuckDuckGo)
    - wikipedia      → Free Wikipedia API
    - crunchbase     → Crunchbase via web search proxy

    Fallback chain:
    Tavily → DuckDuckGo → Hardcoded "data unavailable" with partial report
    """

    def __init__(self):
        super().__init__(agent_id="market_research", timeout=45.0, max_retries=3)

    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        self._log("Planning", f"Breaking down market research tasks for: {company}")

        results = {}

        # ── Step 1: Wikipedia overview ────────────────────
        self._log("Step 1/4", "Fetching company overview from Wikipedia")
        wiki = await self._run_tool_with_retry(
            tool_fn=wikipedia_summary,
            tool_name="wikipedia_summary",
            params_description=f"company={company}",
            fallback_fn=lambda: {"title": company, "summary": "Wikipedia data unavailable.", "url": "", "categories": []},
            tool_args=(company,),
        )
        results["overview"] = wiki

        # ── Step 2: Web search for market context ─────────
        self._log("Step 2/4", "Searching for market size and industry context")
        market_info = await self._run_tool_with_retry(
            tool_fn=web_search,
            tool_name="web_search",
            params_description=f"query='{company} market size industry TAM 2024'",
            fallback_fn=lambda: [],
            tool_args=(f"{company} market size industry total addressable market 2024",),
            tool_kwargs={"max_results": 4},
        )
        results["market_context"] = market_info or []

        # ── Step 3: Competitors ───────────────────────────
        self._log("Step 3/4", "Identifying competitors and market positioning")
        competitors = await self._run_tool_with_retry(
            tool_fn=web_search,
            tool_name="web_search",
            params_description=f"query='{company} competitors alternatives market share'",
            fallback_fn=lambda: [],
            tool_args=(f"{company} main competitors alternatives vs market share",),
            tool_kwargs={"max_results": 5},
        )
        results["competitors"] = competitors or []

        # ── Step 4: Funding history ───────────────────────
        self._log("Step 4/4", "Fetching funding history via Crunchbase proxy")
        funding = await self._run_tool_with_retry(
            tool_fn=crunchbase_lookup,
            tool_name="crunchbase_lookup",
            params_description=f"company={company}",
            fallback_fn=lambda: {"source": "fallback", "results": [], "funding_context": []},
            tool_args=(company,),
        )
        results["funding"] = funding

        # ── A2A: Check inbox for flags from Orchestrator ──
        msg = await self.check_inbox()
        if msg:
            self._log(f"A2A message from {msg.sender}", str(msg.payload), status="info")

        # ── Synthesise summary ────────────────────────────
        self._log("Synthesising", "Compiling market research findings")
        results["summary"] = self._synthesise(company, results)

        self._log("Complete", f"Market research done for {company}", status="success")
        return results

    def _synthesise(self, company: str, data: Dict) -> Dict:
        """Extract the most useful structured data from raw results."""
        overview_text = data.get("overview", {}).get("summary", "No overview available.")

        competitor_names = []
        for r in data.get("competitors", []):
            content = r.get("content", r.get("title", ""))
            if "vs" in content.lower() or "competitor" in content.lower():
                competitor_names.append(r.get("title", "")[:60])

        market_signals = []
        for r in data.get("market_context", []):
            content = r.get("content", "")
            if any(w in content.lower() for w in ["billion", "million", "market", "growth", "%"]):
                market_signals.append(content[:200])

        return {
            "company": company,
            "overview": overview_text[:600],
            "wikipedia_url": data.get("overview", {}).get("url", ""),
            "competitor_snippets": competitor_names[:4],
            "market_size_signals": market_signals[:3],
            "funding_sources": len(data.get("funding", {}).get("results", [])),
        }
