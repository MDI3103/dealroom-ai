"""
Agent 6 — Competitor Intelligence Agent
Automatically finds and analyses top 3 competitors.
"""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List
from agents.base_agent import BaseAgent
from mcp_tools.tools import web_search, get_financial_data, resolve_ticker


class CompetitorAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="competitor", timeout=40.0, max_retries=2)

    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        self._log("Planning", f"Finding top competitors for: {company}")

        # Step 1: Find competitors
        self._log("Step 1/3", "Identifying top competitors")
        comp_search = await self._run_tool_with_retry(
            tool_fn=web_search,
            tool_name="web_search_competitors",
            params_description=f"top competitors of {company}",
            fallback_fn=lambda: [],
            tool_args=(f"{company} top competitors alternatives similar companies",),
            tool_kwargs={"max_results": 5},
        )

        # Extract competitor names from results
        competitors = self._extract_competitor_names(company, comp_search or [])
        self._log("Competitors found", f"Identified: {', '.join(competitors[:3])}", status="success")

        # Step 2: Pull basic data for each competitor
        competitor_data = []
        for comp_name in competitors[:3]:
            self._log(f"Analysing", f"Fetching data for: {comp_name}")
            ticker = await self._run_tool_with_retry(
                tool_fn=resolve_ticker,
                tool_name="resolve_ticker",
                params_description=f"ticker={comp_name}",
                fallback_fn=lambda: None,
                tool_args=(comp_name,),
            )

            fin = {}
            if ticker:
                fin = await self._run_tool_with_retry(
                    tool_fn=get_financial_data,
                    tool_name="yfinance_competitor",
                    params_description=f"ticker={ticker}",
                    fallback_fn=lambda: {},
                    tool_args=(ticker,),
                )

            # Web search for private company data
            if not fin or "error" in fin:
                search = await self._run_tool_with_retry(
                    tool_fn=web_search,
                    tool_name="web_search_comp_data",
                    params_description=f"{comp_name} revenue valuation",
                    fallback_fn=lambda: [],
                    tool_args=(f"{comp_name} revenue valuation funding 2024",),
                    tool_kwargs={"max_results": 2},
                )
                fin = self._extract_basic_financials(comp_name, search or [])

            competitor_data.append({
                "name": comp_name,
                "ticker": ticker,
                "market_cap": self._fmt(fin.get("market_cap")),
                "revenue": self._fmt(fin.get("revenue_ttm") or fin.get("revenue")),
                "sector": fin.get("sector", "N/A"),
                "description": fin.get("description", fin.get("note", ""))[:150],
            })

        # Step 3: Competitive positioning search
        self._log("Step 3/3", "Assessing competitive positioning")
        positioning = await self._run_tool_with_retry(
            tool_fn=web_search,
            tool_name="web_search_positioning",
            params_description=f"{company} market share vs competitors",
            fallback_fn=lambda: [],
            tool_args=(f"{company} market share competitive advantage vs {' vs '.join(competitors[:2])}",),
            tool_kwargs={"max_results": 3},
        )

        summary = self._synthesise(company, competitor_data, positioning or [])
        self._log("Complete", f"Competitor analysis done — {len(competitor_data)} competitors found", status="success")

        return {
            "competitors": competitor_data,
            "positioning_context": positioning or [],
            "summary": summary,
        }

    def _extract_competitor_names(self, company: str, results: List[Dict]) -> List[str]:
        """Extract competitor names from search results."""
        import re
        company_lower = company.lower()
        candidates = []

        # Common competitor patterns in text
        for r in results:
            text = r.get("content", "") + " " + r.get("title", "")
            # Look for "X vs Y" or "alternatives to X" patterns
            vs_matches = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)\b', text)
            for match in vs_matches:
                if (len(match) > 2 and match.lower() != company_lower
                        and match not in ["The", "And", "For", "But", "With", "Inc", "Ltd"]
                        and match not in candidates):
                    candidates.append(match)

        # Return top 3, excluding the company itself
        filtered = [c for c in candidates if company_lower not in c.lower()][:3]

        # Fallback: known competitor pairs
        known = {
            "grab": ["Gojek", "Sea Limited", "Foodpanda"],
            "uber": ["Lyft", "Grab", "Bolt"],
            "airbnb": ["Booking.com", "VRBO", "Expedia"],
            "tesla": ["Rivian", "NIO", "Lucid"],
            "netflix": ["Disney+", "HBO Max", "Amazon Prime"],
            "spotify": ["Apple Music", "Amazon Music", "YouTube Music"],
            "shopify": ["WooCommerce", "BigCommerce", "Magento"],
        }
        fallback = known.get(company.lower(), [])
        if len(filtered) < 3 and fallback:
            for fb in fallback:
                if fb not in filtered:
                    filtered.append(fb)
                if len(filtered) >= 3:
                    break

        return filtered[:3]

    def _extract_basic_financials(self, company: str, results: List[Dict]) -> Dict:
        import re
        for r in results:
            content = r.get("content", "")
            amounts = re.findall(r'\$[\d,.]+\s*(?:billion|million|B|M)', content, re.IGNORECASE)
            if amounts:
                return {"note": f"Est. from web: {amounts[0]}", "revenue": None}
        return {"note": "Private — no public financials", "revenue": None}

    def _fmt(self, val) -> str:
        if val is None:
            return "Private"
        try:
            v = float(val)
            if v >= 1e9: return f"${v/1e9:.1f}B"
            if v >= 1e6: return f"${v/1e6:.0f}M"
            return f"${v:,.0f}"
        except Exception:
            return str(val)

    def _synthesise(self, company: str, competitors: List[Dict], positioning: List[Dict]) -> Dict:
        pos_text = " ".join(r.get("content", "")[:100] for r in positioning[:2])
        return {
            "company": company,
            "competitor_count": len(competitors),
            "competitors": competitors,
            "positioning_snippet": pos_text[:300],
        }
