"""
Agent 3 — Financial Analyst Agent
Tools: yfinance (live data), web_search (fallback for private companies)
Produces: valuation snapshot, revenue, profitability, price history
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from agents.base_agent import BaseAgent
from mcp_tools.tools import (
    get_financial_data,
    get_historical_prices,
    resolve_ticker,
    web_search,
)


class FinancialAnalystAgent(BaseAgent):
    """
    Fetches and analyses financial data for the target company.

    MCP Toolbox:
    - yfinance           → Live financials for public companies
    - web_search         → Fallback for private company funding data

    Fallback chain:
    1. Resolve ticker → yfinance live data
    2. If no ticker → web search for funding/revenue estimates
    3. If both fail → return structured "data unavailable" with explanation

    A2A: Listens for flags from Risk Assessor (e.g. fraud signal)
         and triggers re-analysis of specific financial metrics.
    """

    def __init__(self):
        super().__init__(agent_id="financial_analyst", timeout=45.0, max_retries=3)

    async def _execute(self, company: str, **kwargs) -> Dict[str, Any]:
        self._log("Planning", f"Preparing financial analysis for: {company}")

        results = {}
        ticker = None

        # ── Step 1: Resolve ticker ────────────────────────
        self._log("Step 1/5", "Resolving stock ticker symbol")
        ticker = await self._run_tool_with_retry(
            tool_fn=resolve_ticker,
            tool_name="resolve_ticker",
            params_description=f"company={company}",
            fallback_fn=lambda: None,
            tool_args=(company,),
        )

        if ticker:
            self._log("Ticker resolved", f"Found ticker: {ticker}", status="success")
        else:
            self._warn(
                "Ticker not found",
                f"{company} appears to be a private company — switching to web fallback",
            )

        # ── Step 2: Financial data ────────────────────────
        if ticker:
            self._log("Step 2/5", f"Fetching live financials from yfinance for {ticker}")
            fin_data = await self._run_tool_with_retry(
                tool_fn=get_financial_data,
                tool_name="yfinance_financials",
                params_description=f"ticker={ticker}",
                fallback_fn=lambda: self._private_company_fallback(company),
                tool_args=(ticker,),
            )
        else:
            self._log("Step 2/5", "Public data unavailable — using web search for private financials")
            search_results = await self._run_tool_with_retry(
                tool_fn=web_search,
                tool_name="web_search_financials",
                params_description=f"query='{company} revenue ARR valuation funding 2024'",
                fallback_fn=lambda: [],
                tool_args=(f"{company} revenue annual recurring revenue ARR valuation 2024",),
                tool_kwargs={"max_results": 5},
            )
            fin_data = self._parse_private_financials(company, search_results or [])

        results["financials"] = fin_data

        # ── Step 3: Price history (public only) ──────────
        if ticker:
            self._log("Step 3/5", f"Fetching 1-year price history for {ticker}")
            price_history = await self._run_tool_with_retry(
                tool_fn=get_historical_prices,
                tool_name="yfinance_history",
                params_description=f"ticker={ticker}, period=1y",
                fallback_fn=lambda: {"error": "Price history unavailable"},
                tool_args=(ticker, "1y"),
            )
            results["price_history"] = price_history
        else:
            results["price_history"] = {"note": "Private company — no exchange-listed price history"}

        # ── Step 4: Funding rounds (web search) ──────────
        self._log("Step 4/5", "Searching for funding rounds and investor details")
        funding = await self._run_tool_with_retry(
            tool_fn=web_search,
            tool_name="web_search_funding",
            params_description=f"query='{company} funding rounds Series investors'",
            fallback_fn=lambda: [],
            tool_args=(f"{company} Series A B C funding rounds lead investors total raised",),
            tool_kwargs={"max_results": 4},
        )
        results["funding_rounds"] = funding or []

        # ── Step 5: A2A — check for risk flags ───────────
        self._log("Step 5/5", "Checking A2A inbox for risk flags from Risk Assessor")
        msg = await self.check_inbox()
        if msg and msg.payload.get("flag_type"):
            flag = msg.payload
            self._warn(
                f"A2A FLAG from {msg.sender}",
                f"[{flag.get('severity', 'unknown').upper()}] {flag.get('flag_type')}: {flag.get('detail')}",
            )
            if "revenue" in flag.get("flag_type", "").lower() or "fraud" in flag.get("detail", "").lower():
                self._log("Re-analysis triggered", "Verifying revenue figures due to risk flag")
                verify = await self._run_tool_with_retry(
                    tool_fn=web_search,
                    tool_name="web_search_verify",
                    params_description=f"query='{company} revenue audit actual figures'",
                    fallback_fn=lambda: [],
                    tool_args=(f"{company} revenue actual reported audit financial statement",),
                    tool_kwargs={"max_results": 3},
                )
                results["risk_flag_verification"] = verify

        # ── Synthesise ────────────────────────────────────
        results["summary"] = self._synthesise(company, ticker, results)
        self._log("Complete", f"Financial analysis done for {company}", status="success")
        return results

    def _private_company_fallback(self, company: str) -> Dict:
        return {
            "company_name": company,
            "ticker": None,
            "note": "Private company — financials estimated from public sources",
            "source": "fallback",
        }

    def _parse_private_financials(self, company: str, search_results: list) -> Dict:
        """Extract financial signals from web search results for private companies."""
        import re
        revenue_signals, valuation_signals = [], []

        for r in search_results:
            content = r.get("content", "") + " " + r.get("title", "")
            amounts = re.findall(r'\$[\d,.]+\s*(?:billion|million|B|M|bn|mn)', content, re.IGNORECASE)
            if "valuat" in content.lower() and amounts:
                valuation_signals.extend(amounts[:2])
            if any(w in content.lower() for w in ["revenue", "arr", "gmv"]) and amounts:
                revenue_signals.extend(amounts[:2])

        return {
            "company_name": company,
            "ticker": None,
            "type": "private",
            "revenue_signals": revenue_signals[:3],
            "valuation_signals": valuation_signals[:3],
            "source": "web_search_estimates",
            "note": "Figures estimated from public announcements and reports",
        }

    def _synthesise(self, company: str, ticker: Optional[str], data: Dict) -> Dict:
        fin = data.get("financials", {})
        history = data.get("price_history", {})

        def fmt_currency(val):
            if val is None:
                return "N/A"
            if val >= 1e9:
                return f"${val/1e9:.1f}B"
            if val >= 1e6:
                return f"${val/1e6:.0f}M"
            return f"${val:,.0f}"

        return {
            "company": company,
            "ticker": ticker,
            "is_public": ticker is not None and "error" not in fin,
            "market_cap": fmt_currency(fin.get("market_cap")),
            "revenue_ttm": fmt_currency(fin.get("revenue_ttm")),
            "net_income": fmt_currency(fin.get("net_income")),
            "ebitda": fmt_currency(fin.get("ebitda")),
            "pe_ratio": round(fin.get("pe_ratio", 0), 1) if fin.get("pe_ratio") else "N/A",
            "revenue_growth_pct": round((fin.get("revenue_growth", 0) or 0) * 100, 1),
            "employees": fin.get("employees", "N/A"),
            "sector": fin.get("sector", "N/A"),
            "price_1y_return": history.get("period_return", "N/A"),
            "current_price": history.get("current", "N/A"),
            "currency": fin.get("currency", "USD"),
            "private_valuation_signals": fin.get("valuation_signals", []),
        }
